from __future__ import annotations

from datetime import date, datetime


def test_save_daily_gap_and_delete(components):
    user_id = "wechat-openid-test"
    saved = components.service.save_meal(
        user_id,
        [
            {"food_id": "rice-cooked-white", "grams": 200},
            {"food_id": "chicken-breast-cooked", "grams": 150},
        ],
        eaten_at=datetime(2026, 7, 16, 12, 0, 0),
        source_message_id="msg-1",
    )
    assert saved["saved"] is True
    assert saved["user_key"] != user_id
    assert saved["meal_period"] == "lunch"

    components.service.upsert_profile(
        user_id,
        {
            "daily_energy_kcal": 2000,
            "daily_protein_g": 100,
            "daily_fat_g": 60,
            "daily_carbohydrate_g": 250,
            "daily_fiber_g": 25,
        },
    )
    balance = components.service.get_daily_balance(user_id, date(2026, 7, 16))
    assert balance["meal_count"] == 1
    assert balance["intake"]["energy_kcal"] == 479.5
    assert balance["by_meal_period"]["lunch"]["energy_kcal"] == 479.5
    assert balance["by_meal_period"]["breakfast"]["energy_kcal"] == 0
    assert balance["remaining"]["energy_kcal"] == 1520.5

    gap = components.service.get_nutrient_gap(user_id, date(2026, 7, 14), date(2026, 7, 20))
    assert gap["days_with_records"] == 1
    assert "并非每天" in gap["notes"][0]

    assert components.service.delete_user_data(user_id)["deleted"] is True
    assert components.service.get_daily_balance(user_id, date(2026, 7, 16))["meal_count"] == 0


def test_save_meal_is_idempotent_by_source_message_id(components):
    items = [{"food_id": "rice-cooked-white", "grams": 100}]
    first = components.service.save_meal("u1", items, source_message_id="same-message")
    second = components.service.save_meal("u1", items, source_message_id="same-message")
    assert first["meal_id"] == second["meal_id"]
    assert components.service.get_daily_balance("u1")["meal_count"] == 1


def test_diagnostic_binding_is_pseudonymous_and_alias_cannot_be_stolen(components):
    raw_user_id = "raw-designated-openid"
    assert components.repository.is_diagnostic_alias_bound("your-test-wechat-id") is False
    assert (
        components.repository.bind_diagnostic_test_account(raw_user_id, "your-test-wechat-id")
        is True
    )
    assert components.repository.is_diagnostic_alias_bound("your-test-wechat-id") is True
    assert (
        components.repository.bind_diagnostic_test_account(
            "different-openid", "your-test-wechat-id"
        )
        is False
    )
    assert components.repository.save_diagnostic_message(
        raw_user_id, "inbound", "测试消息", source_message_id="diagnostic-1"
    )
    assert not components.repository.save_diagnostic_message(
        "different-openid", "inbound", "不应保存"
    )
    messages = components.repository.get_diagnostic_messages("your-test-wechat-id")
    assert len(messages) == 1
    assert messages[0]["content"] == "测试消息"
    assert raw_user_id.encode() not in components.settings.database_path.read_bytes()
