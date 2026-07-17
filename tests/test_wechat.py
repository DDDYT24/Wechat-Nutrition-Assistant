from __future__ import annotations

import hashlib
import time

import httpx

from wechat_nutrition_bot.wechat import create_app, verify_signature


def signature(token: str, timestamp: str, nonce: str) -> str:
    return hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode()).hexdigest()


def xml_message(
    content: str,
    msg_id: str = "123",
    create_time: int | None = None,
    user_id: str = "test-user",
) -> str:
    timestamp = create_time or int(time.time())
    return f"""
    <xml>
      <ToUserName>test-account</ToUserName>
      <FromUserName>{user_id}</FromUserName>
      <CreateTime>{timestamp}</CreateTime>
      <MsgType>text</MsgType>
      <Content>{content}</Content>
      <MsgId>{msg_id}</MsgId>
    </xml>
    """


def test_signature_verification():
    value = signature("token", "123", "456")
    assert verify_signature("token", "123", "456", value)
    assert not verify_signature("wrong", "123", "456", value)


async def test_wechat_get_verification(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sig = signature("test-token", "123", "456")
        response = await client.get(
            "/wechat/callback",
            params={
                "signature": sig,
                "timestamp": "123",
                "nonce": "456",
                "echostr": "hello",
            },
        )
    assert response.status_code == 200
    assert response.text == "hello"


async def test_wechat_text_round_trip_and_dedup(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sig = signature("test-token", "123", "456")
        params = {"signature": sig, "timestamp": "123", "nonce": "456"}
        consent = await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message("同意并开始", "msg-consent"),
            headers={"content-type": "application/xml"},
        )
        assert "请按任意顺序" in consent.text
        profile = await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message(
                "男，28岁，175cm，72kg，久坐，增肌，训练2年，每周4天，不适用孕哺",
                "msg-profile",
            ),
            headers={"content-type": "application/xml"},
        )
        assert "请核对资料" in profile.text
        confirmed = await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message("确认资料", "msg-confirm"),
            headers={"content-type": "application/xml"},
        )
        assert "资料已确认" in confirmed.text
        response = await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message("米饭200克，鸡胸肉150克", "msg-wechat-1"),
            headers={"content-type": "application/xml"},
        )
        assert response.status_code == 200
        assert "本餐：480 kcal" in response.text

        duplicate = await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message("米饭200克，鸡胸肉150克", "msg-wechat-1"),
            headers={"content-type": "application/xml"},
        )
    assert "本餐：480 kcal" in duplicate.text
    assert "今日累计：480 kcal" in duplicate.text
    assert app.state.components.service.get_daily_balance("test-user")["meal_count"] == 1


async def test_wechat_rejects_invalid_signature(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/wechat/callback",
            params={"signature": "bad", "timestamp": "123", "nonce": "456"},
            content=xml_message("米饭200克"),
        )
    assert response.status_code == 403


async def test_only_bound_designated_wechat_id_gets_chat_diagnostics(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sig = signature("test-token", "123", "456")
        params = {"signature": sig, "timestamp": "123", "nonce": "456"}
        bound = await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message(
                "绑定测试账号 your-test-wechat-id",
                "bind-designated-account",
                user_id="designated-openid-test",
            ),
            headers={"content-type": "application/xml"},
        )
        assert "已绑定为测试账号 your-test-wechat-id" in bound.text
        await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message(
                "帮助", "designated-help", user_id="designated-openid-test"
            ),
            headers={"content-type": "application/xml"},
        )
        await client.post(
            "/wechat/callback",
            params=params,
            content=xml_message("帮助", "other-help", user_id="other-openid-test"),
            headers={"content-type": "application/xml"},
        )

    messages = app.state.components.repository.get_diagnostic_messages("your-test-wechat-id", 30)
    assert [message["direction"] for message in messages] == [
        "inbound",
        "outbound",
        "inbound",
        "outbound",
    ]
    assert messages[2]["content"] == "帮助"
    assert all("other-openid-test" not in message["content"] for message in messages)
