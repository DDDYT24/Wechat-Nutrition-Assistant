from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from wechat_nutrition_bot.catalog import FoodCatalog
from wechat_nutrition_bot.config import Settings
from wechat_nutrition_bot.wechat import create_app


def test_example_environment_selects_full_v2_catalog():
    project_root = Path(__file__).parents[1]
    example = Settings(_env_file=project_root / ".env.example")
    catalog = FoodCatalog(project_root / example.food_catalog_path)

    assert example.food_catalog_path == Path("data/foods_v2.json")
    assert example.wechat_callback_configured is False
    assert catalog.version == "2.0-cn6"
    assert len(catalog.foods) == 1623


def test_production_rejects_placeholder_secrets(settings):
    unsafe = settings.model_copy(
        update={
            "app_env": "production",
            "user_hmac_secret": "replace-with-a-long-random-secret",
            "wechat_token": "",
        }
    )

    with pytest.raises(RuntimeError, match="Invalid production configuration") as exc_info:
        create_app(unsafe)

    message = str(exc_info.value)
    assert "USER_HMAC_SECRET" in message
    assert "WECHAT_TOKEN" in message
    assert "replace-with-a-long-random-secret" not in message


async def test_internal_bridge_can_be_removed_from_public_deployment(settings):
    production = settings.model_copy(
        update={
            "app_env": "production",
            "user_hmac_secret": "production-test-secret-with-at-least-32-characters",
            "wechat_token": "production-wechat-token",
            "internal_chat_enabled": False,
        }
    )
    app = create_app(production)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        bridge = await client.post(
            "/internal/chat",
            json={"user_id": "test-user", "text": "帮助"},
        )

    assert health.status_code == 200
    assert health.json()["wechat_callback_configured"] is True
    assert health.json()["internal_chat_enabled"] is False
    assert bridge.status_code == 404
