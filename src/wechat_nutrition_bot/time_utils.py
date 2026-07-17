from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MealPeriod = Literal["breakfast", "lunch", "afternoon", "evening"]

MEAL_PERIOD_LABELS: dict[MealPeriod, str] = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "afternoon": "下午加餐",
    "evening": "晚餐/夜间",
}


def as_shanghai(value: datetime | None = None) -> datetime:
    current = value or datetime.now(SHANGHAI_TZ)
    if current.tzinfo is None:
        return current.replace(tzinfo=SHANGHAI_TZ)
    return current.astimezone(SHANGHAI_TZ)


def local_day(value: datetime | None = None) -> date:
    return as_shanghai(value).date()


def classify_meal_period(value: datetime | None = None) -> MealPeriod:
    hour = as_shanghai(value).hour
    if 6 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 14:
        return "lunch"
    if 14 <= hour < 19:
        return "afternoon"
    return "evening"
