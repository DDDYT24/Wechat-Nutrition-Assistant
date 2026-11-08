from datetime import UTC, date, datetime

import pytest


@pytest.mark.parametrize(
    "eaten_at",
    [datetime(2026, 11, 7, 19, 0, tzinfo=UTC), datetime(2026, 11, 8, 3, 0)],
)
def test_meals_use_shanghai_day_and_period(components, eaten_at):
    saved = components.service.save_meal(
        "timezone-user", [{"name": "米饭", "grams": 100}], eaten_at=eaten_at
    )

    assert saved["eaten_at"] == "2026-11-08T03:00:00+08:00"
    assert saved["meal_period"] == "evening"
    assert components.service.get_daily_balance("timezone-user", date(2026, 11, 8))[
        "meal_count"
    ] == 1
    assert components.service.get_daily_balance("timezone-user", date(2026, 11, 7))[
        "meal_count"
    ] == 0


def test_implicit_meal_time_uses_the_reporting_timezone(components, monkeypatch):
    from wechat_nutrition_bot import repository, time_utils

    class ServerClock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 11, 7, 19, 0, tzinfo=UTC)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(repository, "datetime", ServerClock)
    monkeypatch.setattr(time_utils, "datetime", ServerClock)
    saved = components.service.save_meal(
        "server-clock-user", [{"name": "米饭", "grams": 100}]
    )
    assert saved["eaten_at"] == "2026-11-08T03:00:00+08:00"
    assert components.service.get_daily_balance("server-clock-user", date(2026, 11, 8))[
        "meal_count"
    ] == 1
