from pathlib import Path

from wechat_nutrition_bot import config


def test_default_catalog_falls_back_to_the_installed_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FOOD_CATALOG_PATH", raising=False)
    settings = config.Settings(_env_file=None)
    assert settings.food_catalog_path == Path(config.__file__).parent / "data" / "foods_v2.json"


def test_checkout_catalog_remains_the_default_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FOOD_CATALOG_PATH", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "foods_v2.json").write_text("{}", encoding="utf-8")
    assert config.Settings(_env_file=None).food_catalog_path == Path("data/foods_v2.json")
