from __future__ import annotations

from .models import EnergyTargetResult, ProfileDraftData

FORMULA_VERSION = "mifflin-st-jeor-pal-v2"
PAL_BY_ACTIVITY = {
    "sedentary": 1.4,
    "light": 1.55,
    "moderate": 1.7,
    "high": 1.9,
}
GOAL_ADJUSTMENT = {"maintain": 0.0, "lose": -0.15, "gain": 0.08}


def calculate_energy_targets(profile: ProfileDraftData) -> EnergyTargetResult:
    missing = [
        field
        for field in (
            "age",
            "sex",
            "height_cm",
            "weight_kg",
            "activity_level",
            "goal",
            "training_years",
            "training_days_per_week",
        )
        if getattr(profile, field) is None
    ]
    if missing:
        raise ValueError(f"missing required profile fields: {', '.join(missing)}")
    if profile.age is None or profile.age < 18:
        raise ValueError("automated targets are limited to adults age 18 or older")
    if profile.pregnant_or_breastfeeding:
        raise ValueError("pregnancy or breastfeeding requires an individualized professional plan")

    assert profile.sex is not None
    assert profile.weight_kg is not None
    assert profile.height_cm is not None
    assert profile.activity_level is not None
    assert profile.goal is not None
    assert profile.training_days_per_week is not None

    sex_constant = 5 if profile.sex == "male" else -161
    resting = (
        10 * profile.weight_kg
        + 6.25 * profile.height_cm
        - 5 * profile.age
        + sex_constant
    )
    pal = PAL_BY_ACTIVITY[profile.activity_level]
    maintenance = resting * pal
    adjustment = GOAL_ADJUSTMENT[profile.goal]
    target = maintenance * (1 + adjustment)
    warnings: list[str] = []
    if target < resting:
        target = resting
        warnings.append("目标能量已限制为不低于静息能量估算值")

    protein_factor = (
        1.6
        if profile.training_days_per_week > 0 or profile.goal in {"lose", "gain"}
        else 1.2
    )
    protein = profile.weight_kg * protein_factor
    fat = target * 0.25 / 9
    carbohydrate = (target - protein * 4 - fat * 9) / 4
    if carbohydrate < 0:
        raise ValueError("profile produces an invalid macronutrient allocation")
    fiber = target / 1000 * 14

    return EnergyTargetResult(
        formula_version=FORMULA_VERSION,
        resting_energy_kcal=round(resting),
        physical_activity_level=pal,
        maintenance_energy_kcal=round(maintenance),
        goal_adjustment_percent=adjustment * 100,
        target_energy_kcal=round(target),
        protein_g=round(protein, 1),
        fat_g=round(fat, 1),
        carbohydrate_g=round(carbohydrate, 1),
        fiber_g=round(fiber, 1),
        assumptions=[
            "静息能量使用 Mifflin–St Jeor 方程",
            "总能量为静息能量乘以活动系数 PAL",
            "减脂 -15%、增肌 +8% 是 V1.2 的保守产品默认值",
            f"蛋白质按 {protein_factor:.1f} g/kg，脂肪按目标能量 25%，碳水补足剩余能量",
        ],
        warnings=warnings,
    )
