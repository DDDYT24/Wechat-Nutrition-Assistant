from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_path: Path = Path("data/runtime/nutrition_bot.sqlite3")
    food_catalog_path: Path = Path("data/foods_v2.json")
    user_hmac_secret: str = Field(default="development-only-change-me", min_length=16)

    wechat_token: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_sync_timeout_seconds: float = 3.5

    # Retain the historical ``alias`` setting name for environment compatibility,
    # but use a stable WeChat ID as its value rather than a visible nickname.
    diagnostic_test_alias: str = "your-test-wechat-id"
    diagnostic_bind_phrase: str = "绑定测试账号 your-test-wechat-id"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 8.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
