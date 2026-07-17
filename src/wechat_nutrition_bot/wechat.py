from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from defusedxml import ElementTree
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .agent import CONSENT_TEXT, NutritionAgent
from .config import Settings
from .container import Components, build_components
from .time_utils import SHANGHAI_TZ

INTERNAL_CHAT_TOKEN_LABEL = b"personal-wechat-bridge-v1"


class InternalChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=4000)
    message_id: str | None = Field(default=None, min_length=1, max_length=256)
    sent_at: datetime | None = None


class InternalChatResponse(BaseModel):
    reply: str


@dataclass
class WeChatMessage:
    to_user: str
    from_user: str
    create_time: str
    msg_type: str
    content: str = ""
    msg_id: str = ""
    event: str = ""


def verify_signature(token: str, timestamp: str, nonce: str, signature: str) -> bool:
    if not token or not timestamp or not nonce or not signature:
        return False
    digest = hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, signature)


def derive_internal_chat_token(user_hmac_secret: str) -> str:
    """Derive a bridge-only token without introducing another persisted secret."""
    return hmac.new(
        user_hmac_secret.encode("utf-8"), INTERNAL_CHAT_TOKEN_LABEL, hashlib.sha256
    ).hexdigest()


def parse_wechat_xml(body: bytes) -> WeChatMessage:
    root = ElementTree.fromstring(body)

    def value(name: str) -> str:
        node = root.find(name)
        return node.text.strip() if node is not None and node.text else ""

    return WeChatMessage(
        to_user=value("ToUserName"),
        from_user=value("FromUserName"),
        create_time=value("CreateTime"),
        msg_type=value("MsgType").lower(),
        content=value("Content"),
        msg_id=value("MsgId"),
        event=value("Event").lower(),
    )


def text_reply(message: WeChatMessage, content: str) -> str:
    safe_content = html.escape(content, quote=False)
    return (
        "<xml>"
        f"<ToUserName>{html.escape(message.from_user)}</ToUserName>"
        f"<FromUserName>{html.escape(message.to_user)}</FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType>text</MsgType>"
        f"<Content>{safe_content}</Content>"
        "</xml>"
    )


async def _finish_in_background(
    components: Components,
    agent: NutritionAgent,
    message: WeChatMessage,
) -> None:
    request_id = message.msg_id or f"{message.from_user}:{message.create_time}"
    try:
        result = await agent.handle_text(
            message.from_user,
            message.content,
            request_id,
            _message_datetime(message),
        )
        components.repository.set_async_result(message.from_user, request_id, "complete", result)
    except Exception:
        components.repository.set_async_result(
            message.from_user,
            request_id,
            "failed",
            "本次分析失败，请检查食物名称和克数后重新发送。",
        )


def _message_datetime(message: WeChatMessage) -> datetime:
    try:
        return datetime.fromtimestamp(int(message.create_time), UTC).astimezone(SHANGHAI_TZ)
    except (TypeError, ValueError, OSError):
        return datetime.now(SHANGHAI_TZ)


def create_app(settings: Settings | None = None) -> FastAPI:
    components = build_components(settings)
    agent = NutritionAgent(
        components.service, components.deepseek, components.profile_parser
    )
    app = FastAPI(title="WeChat Nutrition Bot", version="1.1.0")
    app.state.components = components
    app.state.agent = agent

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": "1.1.0",
            "deepseek_configured": components.deepseek.enabled,
            "catalog_version": components.catalog.version,
        }

    @app.post("/internal/chat", response_model=InternalChatResponse)
    async def internal_chat(
        payload: InternalChatRequest,
        bridge_token: str = Header(default="", alias="X-Nutrition-Bridge-Token"),
    ) -> InternalChatResponse:
        expected_token = derive_internal_chat_token(components.settings.user_hmac_secret)
        if not hmac.compare_digest(
            bridge_token.encode("utf-8"), expected_token.encode("ascii")
        ):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        reply = await agent.handle_text(
            payload.user_id,
            payload.text,
            payload.message_id,
            payload.sent_at,
        )
        return InternalChatResponse(reply=reply)

    @app.get("/wechat/callback", response_class=Response)
    async def verify_wechat(
        signature: str = Query(default=""),
        timestamp: str = Query(default=""),
        nonce: str = Query(default=""),
        echostr: str = Query(default=""),
    ) -> Response:
        if not verify_signature(components.settings.wechat_token, timestamp, nonce, signature):
            raise HTTPException(status_code=403, detail="invalid signature")
        return Response(content=echostr, media_type="text/plain")

    @app.post("/wechat/callback", response_class=Response)
    async def receive_wechat(
        request: Request,
        background_tasks: BackgroundTasks,
        signature: str = Query(default=""),
        timestamp: str = Query(default=""),
        nonce: str = Query(default=""),
        encrypt_type: str = Query(default=""),
    ) -> Response:
        if encrypt_type:
            raise HTTPException(status_code=400, detail="V1.1 only supports plaintext mode")
        if not verify_signature(components.settings.wechat_token, timestamp, nonce, signature):
            raise HTTPException(status_code=403, detail="invalid signature")
        try:
            message = parse_wechat_xml(await request.body())
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid XML") from exc

        receipt_id = message.msg_id or f"{message.from_user}:{message.create_time}:{message.event}"
        existing = components.repository.get_message_receipt(receipt_id)
        if existing:
            return Response(content=text_reply(message, existing), media_type="application/xml")

        is_binding_message = (
            message.msg_type == "text"
            and message.content.strip() == components.settings.diagnostic_bind_phrase
        )
        if is_binding_message:
            bound = components.repository.bind_diagnostic_test_account(
                message.from_user, components.settings.diagnostic_test_alias
            )
            if bound:
                components.repository.save_diagnostic_message(
                    message.from_user,
                    "inbound",
                    message.content,
                    message_type="text",
                    source_message_id=receipt_id,
                    created_at=_message_datetime(message),
                )
                reply = (
                    f"已绑定为测试账号 {components.settings.diagnostic_test_alias}。"
                    "之后与公众号的收发消息会仅在本机脱敏保存，用于问题排查。"
                )
            else:
                reply = "该测试账号别名已绑定，不能由另一个微信账号覆盖。"
        elif message.msg_type == "event":
            if message.event == "subscribe":
                state = components.service.get_onboarding_status(message.from_user)
                if state["profile_confirmed"]:
                    reply = "欢迎回来。发送“帮助”查看记录方式。"
                else:
                    reply = CONSENT_TEXT
            else:
                return Response(content="success", media_type="text/plain")
        elif message.msg_type in {"image", "voice", "video", "shortvideo"}:
            reply = "V1.1 暂不读取图片或语音。请改用文字，并写明食物、克数、烹饪方式和用油量。"
        elif message.msg_type != "text":
            reply = "V1.1 目前只处理文字饮食记录。发送“帮助”查看示例。"
        else:
            components.repository.save_diagnostic_message(
                message.from_user,
                "inbound",
                message.content,
                message_type="text",
                source_message_id=receipt_id,
                created_at=_message_datetime(message),
            )
            try:
                reply = await asyncio.wait_for(
                    agent.handle_text(
                        message.from_user,
                        message.content,
                        receipt_id,
                        _message_datetime(message),
                    ),
                    timeout=components.settings.wechat_sync_timeout_seconds,
                )
            except TimeoutError:
                components.repository.set_async_result(
                    message.from_user, receipt_id, "pending", None
                )
                background_tasks.add_task(_finish_in_background, components, agent, message)
                reply = "已收到，正在分析。约十秒后发送“结果”获取本次分析。"

        components.repository.save_diagnostic_message(
            message.from_user,
            "outbound",
            reply,
            message_type="text",
            source_message_id=receipt_id,
            created_at=datetime.now(SHANGHAI_TZ),
        )
        components.repository.save_message_receipt(receipt_id, reply)
        return Response(content=text_reply(message, reply), media_type="application/xml")

    return app


app = create_app()
