from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCTION_ENVIRONMENTS = {"prod", "production"}
INSECURE_HMAC_SECRETS = {
    "development-only-change-me",
    "replace-with-a-long-random-secret",
}


def default_food_catalog_path() -> Path:
    local_catalog = Path("data/foods_v2.json")
    if local_catalog.is_file():
        return local_catalog
    return Path(__file__).parent / "data" / "foods_v2.json"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    internal_chat_enabled: bool = True
    database_path: Path = Path("data/runtime/nutrition_bot.sqlite3")
    food_catalog_path: Path = Field(default_factory=default_food_catalog_path)
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

    @property
    def wechat_callback_configured(self) -> bool:
        token = self.wechat_token.strip().lower()
        return bool(token) and not token.startswith("replace-with-")

    def production_configuration_errors(self) -> list[str]:
        """Return actionable errors that would make a public deployment unsafe or unusable."""
        if self.app_env.strip().lower() not in PRODUCTION_ENVIRONMENTS:
            return []

        errors: list[str] = []
        secret = self.user_hmac_secret.strip()
        if len(secret) < 32 or secret.lower() in INSECURE_HMAC_SECRETS:
            errors.append(
                "USER_HMAC_SECRET must be a unique random value of at least 32 characters"
            )
        if not self.wechat_callback_configured:
            errors.append("WECHAT_TOKEN must match the token configured in the WeChat console")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()
