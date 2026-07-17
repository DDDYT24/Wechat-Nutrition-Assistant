from __future__ import annotations

from datetime import datetime

import pytest

from wechat_nutrition_bot.energy import calculate_energy_targets
from wechat_nutrition_bot.models import ProfileDraftData
from wechat_nutrition_bot.time_utils import SHANGHAI_TZ, classify_meal_period


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (5, 59, "evening"),
        (6, 0, "breakfast"),
        (10, 59, "breakfast"),
        (11, 0, "lunch"),
        (13, 59, "lunch"),
        (14, 0, "afternoon"),
        (18, 59, "afternoon"),
        (19, 0, "evening"),
    ],
)
def test_meal_period_boundaries(hour, minute, expected):
    value = datetime(2026, 7, 16, hour, minute, tzinfo=SHANGHAI_TZ)
    assert classify_meal_period(value) == expected


def test_mifflin_energy_and_macros_are_reproducible():
    result = calculate_energy_targets(
        ProfileDraftData(
            age=28,
            sex="male",
            height_cm=175,
            weight_kg=72,
            activity_level="sedentary",
            goal="gain",
            training_years=2,
            training_days_per_week=4,
            pregnant_or_breastfeeding=False,
        )
    )
    assert result.resting_energy_kcal == 1679
    assert result.maintenance_energy_kcal == 2350
    assert result.target_energy_kcal == 2538
    macro_energy = result.protein_g * 4 + result.fat_g * 9 + result.carbohydrate_g * 4
    assert macro_energy == pytest.approx(result.target_energy_kcal, abs=1)


def test_automated_target_rejects_minor_and_pregnancy():
    base = {
        "sex": "female",
        "height_cm": 165,
        "weight_kg": 60,
        "activity_level": "light",
        "goal": "maintain",
        "training_years": 1,
        "training_days_per_week": 3,
    }
    with pytest.raises(ValueError, match="18"):
        calculate_energy_targets(ProfileDraftData(age=17, **base))
    with pytest.raises(ValueError, match="pregnancy"):
        calculate_energy_targets(
            ProfileDraftData(age=28, pregnant_or_breastfeeding=True, **base)
        )
