from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Nutrients(BaseModel):
    energy_kcal: float = Field(default=0, ge=0)
    protein_g: float = Field(default=0, ge=0)
    fat_g: float = Field(default=0, ge=0)
    carbohydrate_g: float = Field(default=0, ge=0)
    fiber_g: float = Field(default=0, ge=0)

    def scaled(self, factor: float) -> Nutrients:
        return Nutrients(
            **{key: round(value * factor, 3) for key, value in self.model_dump().items()}
        )

    def plus(self, other: Nutrients) -> Nutrients:
        return Nutrients(
            **{
                key: round(getattr(self, key) + getattr(other, key), 3)
                for key in type(self).model_fields
            }
        )


class FoodRecord(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    nutrients_per_100g: Nutrients
    source: str
    data_status: Literal["seed", "verified", "label", "published", "estimated"] = "seed"
    notes: str = ""


class ParsedMealItem(BaseModel):
    name: str
    grams: float | None = Field(default=None, gt=0, le=5000)
    cooking_method: str | None = None
    brand: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> object:
        if isinstance(value, str):
            mapped = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(value.strip().lower())
            if mapped is not None:
                return mapped
            try:
                return float(value)
            except ValueError:
                return 0.5
        return value


class MealParseResult(BaseModel):
    items: list[ParsedMealItem] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    parser: Literal["rules", "deepseek", "hybrid"] = "rules"
    notes: list[str] = Field(default_factory=list)


class IntentMealItem(BaseModel):
    """LLM-extracted meal mention before catalog resolution or estimation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    raw_name: str = Field(min_length=1, max_length=100)
    catalog_name: str | None = Field(default=None, max_length=100)
    amount: float | None = Field(default=None, gt=0, le=5000)
    unit: str | None = Field(default=None, max_length=20)
    explicit_grams: float | None = Field(default=None, gt=0, le=5000)
    cooking_method: str | None = Field(default=None, max_length=40)
    needs_clarification: bool = False


class IntentExercise(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["力量训练", "有氧", "HIIT", "柔韧", "其他"]
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    intensity: Literal["低", "中", "高"] = "中"
    body_parts: list[str] = Field(default_factory=list, max_length=20)
    exercises: list[str] = Field(default_factory=list, max_length=50)
    steps: int | None = Field(default=None, ge=0, le=200000)


class StructuredIntentResult(BaseModel):
    """Strict multi-intent plan used before catalog lookup and optional estimation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    intent_types: list[
        Literal["meal_record", "training", "query", "emotion", "profile", "other"]
    ] = Field(default_factory=list, max_length=6)
    meal_text: str | None = Field(default=None, max_length=4000)
    meal_items: list[IntentMealItem] = Field(default_factory=list, max_length=50)
    exercise_text: str | None = Field(default=None, max_length=4000)
    exercise: IntentExercise | None = None
    parser: Literal["rules", "deepseek"] = "deepseek"
    notes: list[str] = Field(default_factory=list, max_length=20)


class MealItemInput(BaseModel):
    food_id: str | None = None
    name: str | None = None
    grams: float = Field(gt=0, le=5000)
    cooking_method: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def require_identifier(self) -> MealItemInput:
        if not self.food_id and not self.name:
            raise ValueError("food_id or name is required")
        return self


class CalculatedMealItem(BaseModel):
    food_id: str
    food_name: str
    grams: float
    nutrients: Nutrients
    source: str
    data_status: str
    calculation: str


class MealCalculation(BaseModel):
    items: list[CalculatedMealItem]
    totals: Nutrients
    unresolved: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: Literal["complete", "partial", "needs_clarification"]


class UserProfileInput(BaseModel):
    age: int | None = Field(default=None, ge=18, le=100)
    sex: Literal["female", "male", "unspecified"] = "unspecified"
    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=25, le=400)
    activity_level: Literal[
        "sedentary", "light", "moderate", "high", "unspecified"
    ] = "unspecified"
    goal: Literal["maintain", "lose", "gain", "unspecified"] = "unspecified"
    training_years: float | None = Field(default=None, ge=0, le=80)
    training_days_per_week: int | None = Field(default=None, ge=0, le=7)
    training_minutes_per_session: int | None = Field(default=None, ge=0, le=600)
    target_weight_kg: float | None = Field(default=None, ge=25, le=400)
    pregnant_or_breastfeeding: bool = False
    health_conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    dietary_preferences: list[str] = Field(default_factory=list)
    daily_energy_kcal: float | None = Field(default=None, ge=800, le=6000)
    daily_protein_g: float | None = Field(default=None, ge=10, le=500)
    daily_fat_g: float | None = Field(default=None, ge=10, le=300)
    daily_carbohydrate_g: float | None = Field(default=None, ge=20, le=1000)
    daily_fiber_g: float | None = Field(default=None, ge=5, le=100)
    allergies: list[str] = Field(default_factory=list)
    notes: str = ""
    formula_version: str | None = None
    resting_energy_kcal: float | None = Field(default=None, ge=500, le=5000)
    physical_activity_level: float | None = Field(default=None, ge=1.0, le=2.5)
    maintenance_energy_kcal: float | None = Field(default=None, ge=800, le=8000)
    confirmed_at: datetime | None = None

    @field_validator("activity_level", mode="before")
    @classmethod
    def migrate_activity_level(cls, value: object) -> object:
        return "sedentary" if value == "low" else value


class ProfileDraftData(BaseModel):
    """Partially collected input; safety gates are applied before confirmation."""

    age: int | None = Field(default=None, ge=1, le=120)
    sex: Literal["female", "male"] | None = None
    height_cm: float | None = Field(default=None, ge=80, le=250)
    weight_kg: float | None = Field(default=None, ge=15, le=400)
    activity_level: Literal["sedentary", "light", "moderate", "high"] | None = None
    goal: Literal["maintain", "lose", "gain"] | None = None
    training_years: float | None = Field(default=None, ge=0, le=80)
    training_days_per_week: int | None = Field(default=None, ge=0, le=7)
    training_minutes_per_session: int | None = Field(default=None, ge=0, le=600)
    target_weight_kg: float | None = Field(default=None, ge=15, le=400)
    pregnant_or_breastfeeding: bool | None = None
    health_conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    dietary_preferences: list[str] = Field(default_factory=list)
    notes: str = ""


class ProfileDraft(BaseModel):
    status: Literal["awaiting_consent", "collecting", "awaiting_confirmation", "confirmed"]
    data: ProfileDraftData = Field(default_factory=ProfileDraftData)
    consented_at: datetime | None = None
    updated_at: datetime


class EnergyTargetResult(BaseModel):
    formula_version: str
    resting_energy_kcal: float
    physical_activity_level: float
    maintenance_energy_kcal: float
    goal_adjustment_percent: float
    target_energy_kcal: float
    protein_g: float
    fat_g: float
    carbohydrate_g: float
    fiber_g: float
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CustomFoodInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    brand: str = Field(default="", max_length=80)
    aliases: list[str] = Field(default_factory=list)
    nutrients_per_100g: Nutrients
    notes: str = ""
    origin: Literal["label", "llm_estimate"] = "label"


class EstimatedFoodItem(BaseModel):
    """Model estimate for an unresolved food, validated before persistence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    grams: float = Field(gt=0, le=5000)
    nutrients_per_100g: Nutrients
    confidence: float = Field(ge=0, le=1)
    assumptions: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def validate_per_100g_estimate(self) -> EstimatedFoodItem:
        nutrients = self.nutrients_per_100g
        if nutrients.energy_kcal > 1000:
            raise ValueError("estimated energy per 100g exceeds plausible bounds")
        if any(
            getattr(nutrients, field) > 100
            for field in ("protein_g", "fat_g", "carbohydrate_g", "fiber_g")
        ):
            raise ValueError("estimated nutrient per 100g exceeds plausible bounds")
        return self


class EstimatedMealResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    items: list[EstimatedFoodItem] = Field(default_factory=list, max_length=30)
    notes: list[str] = Field(default_factory=list, max_length=20)


class SavedMeal(BaseModel):
    meal_id: str
    user_key: str
    eaten_at: datetime
    meal_period: Literal["breakfast", "lunch", "afternoon", "evening"]
    calculation: MealCalculation


class DailyBalance(BaseModel):
    user_key: str
    day: date
    intake: Nutrients
    targets: Nutrients | None = None
    remaining: Nutrients | None = None
    meal_count: int
    by_meal_period: dict[str, Nutrients] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class NutrientGap(BaseModel):
    user_key: str
    start_date: date
    end_date: date
    days_with_records: int
    daily_average: Nutrients
    targets: Nutrients | None = None
    gaps: Nutrients | None = None
    notes: list[str] = Field(default_factory=list)
