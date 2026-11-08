from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import TypeAdapter

from .catalog import FoodCatalog
from .energy import calculate_energy_targets
from .exercise import ExerciseService, ExerciseSession
from .models import (
    CustomFoodInput,
    MealItemInput,
    ProfileDraftData,
    UserProfileInput,
)
from .nutrition import NutritionCalculator
from .parser import MealParser
from .repository import Repository
from .time_utils import as_shanghai, local_day

MEAL_ITEMS_ADAPTER = TypeAdapter(list[MealItemInput])
REQUIRED_PROFILE_FIELDS = (
    "age",
    "sex",
    "height_cm",
    "weight_kg",
    "activity_level",
    "goal",
    "training_years",
    "training_days_per_week",
    "pregnant_or_breastfeeding",
)
HIGH_RISK_TERMS = (
    "进食障碍",
    "厌食",
    "暴食",
    "肾病",
    "肾功能",
    "透析",
    "肝衰",
    "糖尿病用药",
)


class NutritionService:
    """Application service shared by WeChat, MCP, tests and future channels."""

    def __init__(
        self,
        catalog: FoodCatalog,
        calculator: NutritionCalculator,
        parser: MealParser,
        repository: Repository,
    ):
        self.catalog = catalog
        self.calculator = calculator
        self.parser = parser
        self.repository = repository

    def lookup_food(self, query: str, limit: int = 5) -> dict[str, Any]:
        return {
            "query": query,
            "catalog_version": self.catalog.version,
            "disclaimer": self.catalog.disclaimer,
            "matches": self.catalog.search(query, limit),
        }

    async def parse_meal(self, text: str, user_id: str | None = None) -> dict[str, Any]:
        additional_names = None
        if user_id:
            additional_names = [food.name for food in self.repository.list_custom_foods(user_id)]
        return (await self.parser.parse(text, additional_names)).model_dump()

    def calculate_meal(
        self,
        items: list[dict[str, Any]] | list[MealItemInput],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        validated = MEAL_ITEMS_ADAPTER.validate_python(items)
        additional = self.repository.list_custom_foods(user_id) if user_id else None
        return self.calculator.calculate(validated, additional).model_dump()

    def save_meal(
        self,
        user_id: str,
        items: list[dict[str, Any]] | list[MealItemInput],
        eaten_at: datetime | None = None,
        note: str = "",
        source_message_id: str | None = None,
    ) -> dict[str, Any]:
        validated = MEAL_ITEMS_ADAPTER.validate_python(items)
        additional = self.repository.list_custom_foods(user_id)
        calculation = self.calculator.calculate(validated, additional)
        if calculation.unresolved:
            return {
                "saved": False,
                "reason": "存在未命中的食物，不能将不确定数字写入饮食记录",
                "calculation": calculation.model_dump(),
            }
        saved = self.repository.save_meal(
            user_id,
            calculation,
            eaten_at=eaten_at,
            note=note,
            source_message_id=source_message_id,
        )
        return {"saved": True, **saved.model_dump(mode="json")}

    def get_daily_balance(self, user_id: str, day: date | None = None) -> dict[str, Any]:
        balance = self.repository.get_daily_balance(user_id, day or local_day())
        return balance.model_dump(mode="json")

    def record_exercise(
        self,
        user_id: str,
        session: ExerciseSession,
        exercised_at: datetime | None = None,
        source_message_id: str | None = None,
    ) -> dict[str, object]:
        profile = self.repository.get_profile(user_id)
        weight = profile.weight_kg if profile else None
        estimated_energy = None
        if weight and session.duration_minutes:
            estimated_energy = ExerciseService.estimate_training_kcal(
                session.type,
                session.duration_minutes,
                weight,
                session.intensity,
            )
        return self.repository.save_exercise_session(
            user_id,
            session,
            as_shanghai(exercised_at),
            estimated_energy_kcal=estimated_energy,
            source_message_id=source_message_id,
        )

    def get_daily_exercise(
        self, user_id: str, day: date | None = None
    ) -> list[dict[str, object]]:
        return self.repository.get_exercise_sessions(user_id, day or local_day())

    def get_nutrient_gap(self, user_id: str, start_date: date, end_date: date) -> dict[str, Any]:
        return self.repository.get_nutrient_gap(user_id, start_date, end_date).model_dump(
            mode="json"
        )

    def generate_weekly_review(
        self, user_id: str, week_start: date | None = None
    ) -> dict[str, Any]:
        today = local_day()
        start = week_start or (today - timedelta(days=today.weekday()))
        end = start + timedelta(days=6)
        gap = self.repository.get_nutrient_gap(user_id, start, end)
        avg = gap.daily_average
        lines = [
            f"{start.isoformat()} 至 {end.isoformat()}：有 {gap.days_with_records} 天饮食记录。",
            (
                f"有记录日期的日均摄入：{avg.energy_kcal:.0f} kcal，蛋白质 {avg.protein_g:.1f} g，"
                f"脂肪 {avg.fat_g:.1f} g，碳水 {avg.carbohydrate_g:.1f} g，"
                f"膳食纤维 {avg.fiber_g:.1f} g。"
            ),
        ]
        if gap.targets and gap.gaps:
            lines.append("缺口只依据用户自行设置的目标计算，不构成医学营养处方。")
        lines.extend(gap.notes)
        return {
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "data": gap.model_dump(mode="json"),
            "review": "\n".join(lines),
        }

    def upsert_profile(
        self, user_id: str, profile: dict[str, Any] | UserProfileInput
    ) -> dict[str, Any]:
        validated = UserProfileInput.model_validate(profile)
        key = self.repository.upsert_profile(user_id, validated)
        return {"saved": True, "user_key": key, "profile": validated.model_dump()}

    def get_onboarding_status(self, user_id: str) -> dict[str, Any]:
        draft = self.repository.get_profile_draft(user_id)
        profile = self.repository.get_profile(user_id)
        profile_confirmed = bool(profile and profile.confirmed_at)
        status = (
            draft.status
            if draft
            else ("confirmed" if profile_confirmed else "awaiting_consent")
        )
        return {
            "status": status,
            "draft": draft.data.model_dump() if draft else None,
            "profile_confirmed": profile_confirmed,
            "missing_fields": self.missing_profile_fields(draft.data) if draft else [],
        }

    @staticmethod
    def missing_profile_fields(data: ProfileDraftData) -> list[str]:
        return [field for field in REQUIRED_PROFILE_FIELDS if getattr(data, field) is None]

    def begin_onboarding(self, user_id: str) -> dict[str, Any]:
        existing = self.repository.get_profile_draft(user_id)
        data = existing.data if existing else ProfileDraftData()
        draft = self.repository.save_profile_draft(
            user_id, data, "collecting", consented_at=datetime.now(UTC)
        )
        return draft.model_dump(mode="json")

    def record_profile_input(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        current = self.repository.get_profile_draft(user_id)
        if not current or not current.consented_at:
            raise ValueError("profile consent is required before collecting data")
        payload = current.data.model_dump()
        payload.update({key: value for key, value in updates.items() if key in payload})
        data = ProfileDraftData.model_validate(payload)
        missing = self.missing_profile_fields(data)
        status = "collecting" if missing else "awaiting_confirmation"
        saved = self.repository.save_profile_draft(user_id, data, status)
        return {**saved.model_dump(mode="json"), "missing_fields": missing}

    def calculate_energy_targets(
        self, profile: dict[str, Any] | ProfileDraftData
    ) -> dict[str, Any]:
        data = ProfileDraftData.model_validate(profile)
        return calculate_energy_targets(data).model_dump()

    def confirm_profile(self, user_id: str) -> dict[str, Any]:
        draft = self.repository.get_profile_draft(user_id)
        if not draft or draft.status != "awaiting_confirmation":
            raise ValueError("profile is not ready for confirmation")
        missing = self.missing_profile_fields(draft.data)
        if missing:
            raise ValueError(f"missing required profile fields: {', '.join(missing)}")
        condition_text = " ".join(draft.data.health_conditions)
        if any(term in condition_text for term in HIGH_RISK_TERMS):
            raise ValueError("该健康情况需要医生或注册营养师制定个体化目标")
        targets = calculate_energy_targets(draft.data)
        payload = draft.data.model_dump()
        payload.update(
            {
                "daily_energy_kcal": targets.target_energy_kcal,
                "daily_protein_g": targets.protein_g,
                "daily_fat_g": targets.fat_g,
                "daily_carbohydrate_g": targets.carbohydrate_g,
                "daily_fiber_g": targets.fiber_g,
                "formula_version": targets.formula_version,
                "resting_energy_kcal": targets.resting_energy_kcal,
                "physical_activity_level": targets.physical_activity_level,
                "maintenance_energy_kcal": targets.maintenance_energy_kcal,
                "confirmed_at": datetime.now(UTC),
            }
        )
        profile = UserProfileInput.model_validate(payload)
        self.repository.upsert_profile(user_id, profile)
        self.repository.save_profile_draft(user_id, draft.data, "confirmed")
        assert profile.weight_kg is not None
        self.repository.record_weight(user_id, profile.weight_kg, as_shanghai())
        return {
            "confirmed": True,
            "profile": profile.model_dump(mode="json"),
            "targets": targets.model_dump(),
        }

    def register_custom_food(
        self, user_id: str, food: dict[str, Any] | CustomFoodInput
    ) -> dict[str, Any]:
        validated = CustomFoodInput.model_validate(food)
        saved = self.repository.upsert_custom_food(user_id, validated)
        return {"saved": True, "food": saved.model_dump()}

    def list_custom_foods(self, user_id: str) -> dict[str, Any]:
        return {
            "foods": [food.model_dump() for food in self.repository.list_custom_foods(user_id)]
        }

    def record_weight(
        self, user_id: str, weight_kg: float, measured_at: datetime | None = None
    ) -> dict[str, Any]:
        timestamp = as_shanghai(measured_at)
        self.repository.record_weight(user_id, weight_kg, timestamp)
        return {"saved": True, "weight_kg": weight_kg, "measured_at": timestamp.isoformat()}

    def get_weight_trend(self, user_id: str, limit: int = 28) -> dict[str, Any]:
        records = self.repository.get_weight_records(user_id, limit)
        change = None
        if len(records) >= 2:
            change = round(float(records[-1]["weight_kg"]) - float(records[0]["weight_kg"]), 2)
        return {
            "records": records,
            "count": len(records),
            "change_kg": change,
            "ready_for_target_calibration": len(records) >= 14,
            "note": "至少14天且饮食记录较完整后才考虑小幅校准目标。",
        }

    def delete_user_data(self, user_id: str) -> dict[str, Any]:
        return {"deleted": self.repository.delete_user_data(user_id)}
