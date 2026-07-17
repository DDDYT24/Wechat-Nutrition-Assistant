from __future__ import annotations

from datetime import date, datetime

import httpx

from wechat_nutrition_bot.wechat import create_app, derive_internal_chat_token


def bridge_headers(settings) -> dict[str, str]:
    return {
        "X-Nutrition-Bridge-Token": derive_internal_chat_token(settings.user_hmac_secret)
    }


async def post_internal(client: httpx.AsyncClient, settings, payload: dict[str, object]):
    return await client.post(
        "/internal/chat",
        json=payload,
        headers=bridge_headers(settings),
    )


async def complete_onboarding(client: httpx.AsyncClient, settings, user_id: str) -> None:
    await post_internal(
        client,
        settings,
        {"user_id": user_id, "text": "同意并开始", "message_id": "bridge-consent"},
    )
    await post_internal(
        client,
        settings,
        {
            "user_id": user_id,
            "text": "男，28岁，175cm，72kg，久坐，增肌，训练2年，每周4天，不适用孕哺",
            "message_id": "bridge-profile",
        },
    )
    response = await post_internal(
        client,
        settings,
        {"user_id": user_id, "text": "确认资料", "message_id": "bridge-confirm"},
    )
    assert response.status_code == 200
    assert "资料已确认" in response.json()["reply"]


async def test_internal_chat_accepts_derived_bridge_token_and_sent_at(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await post_internal(
            client,
            settings,
            {
                "user_id": "personal-wechat-user",
                "text": "同意并开始",
                "message_id": "bridge-message-1",
                "sent_at": "2026-07-16T08:30:00+08:00",
            },
        )

    assert response.status_code == 200
    assert "请按任意顺序" in response.json()["reply"]


async def test_internal_chat_rejects_missing_or_invalid_bridge_token(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    payload = {"user_id": "unauthorized-user", "text": "同意并开始"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.post("/internal/chat", json=payload)
        invalid = await client.post(
            "/internal/chat",
            json=payload,
            headers={"X-Nutrition-Bridge-Token": "wrong-token"},
        )

    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert app.state.components.service.get_onboarding_status("unauthorized-user")[
        "status"
    ] == "awaiting_consent"


async def test_internal_chat_never_persists_raw_user_id(settings):
    raw_user_id = "wxid-raw-must-never-be-stored"
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await post_internal(
            client,
            settings,
            {"user_id": raw_user_id, "text": "同意并开始", "message_id": "privacy-1"},
        )

    assert response.status_code == 200
    with app.state.components.repository.connection() as connection:
        user_keys = {
            row["user_key"]
            for table in ("users", "profile_drafts")
            for row in connection.execute(f"SELECT user_key FROM {table}").fetchall()
        }
    assert raw_user_id not in user_keys
    assert app.state.components.repository.user_key(raw_user_id) in user_keys
    assert raw_user_id.encode("utf-8") not in settings.database_path.read_bytes()


async def test_internal_chat_preserves_meal_idempotency(settings):
    user_id = "personal-wechat-idempotent-user"
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await complete_onboarding(client, settings, user_id)
        payload = {
            "user_id": user_id,
            "text": "米饭200克，鸡胸肉150克",
            "message_id": "personal-wechat-meal-1",
            "sent_at": datetime(2026, 7, 16, 8, 30).isoformat(),
        }
        first = await post_internal(client, settings, payload)
        duplicate = await post_internal(client, settings, payload)

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert "早餐已记录" in first.json()["reply"]
    assert "今日累计：480 kcal" in duplicate.json()["reply"]
    assert app.state.components.service.get_daily_balance(
        user_id, date(2026, 7, 16)
    )["meal_count"] == 1
