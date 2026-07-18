from __future__ import annotations

from pathlib import Path

import pytest

from wechat_nutrition_bot.catalog import FoodCatalog
from wechat_nutrition_bot.config import Settings
from wechat_nutrition_bot.container import Components, build_components


@pytest.fixture
def food_catalog_path() -> Path:
    return Path(__file__).parents[1] / "data" / "foods_v1.json"


@pytest.fixture
def settings(tmp_path: Path, food_catalog_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "test.sqlite3",
        food_catalog_path=food_catalog_path,
        user_hmac_secret="test-secret-that-is-long-enough",
        wechat_token="test-token",
        deepseek_api_key="",
        app_env="test",
    )


@pytest.fixture
def components(settings: Settings) -> Components:
    return build_components(settings)


@pytest.fixture
def catalog(food_catalog_path: Path) -> FoodCatalog:
    return FoodCatalog(food_catalog_path)
