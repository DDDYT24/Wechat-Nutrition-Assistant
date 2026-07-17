from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .deepseek import DeepSeekClient
from .models import CustomFoodInput, MealItemInput, Nutrients
from .profile_parser import ProfileParser
from .service import NutritionService
from .time_utils import MEAL_PERIOD_LABELS, local_day

CONSENT_TEXT = (
    "欢迎使用微信营养记录助手 V1.1。\n"
    "为了估算每日目标并记录饮食，需要保存你的年龄、生理性别、身高、体重、活动与训练情况。"
    "微信标识会经 HMAC 匿名化，资料只用于本功能；可随时发送“删除全部数据”。\n"
    "本工具面向一般健康成年人，不替代医生或注册营养师。若同意，请回复：同意并开始"
)

PROFILE_PROMPT = (
    "请按任意顺序发送，也可以分多条：\n"
    "年龄；生理性别；身高cm；体重kg；日常活动（久坐/轻活动/中等活动/高活动）；"
    "目标（减脂/增肌/维持）；训练几年；每周训练几天；是否处于孕期或哺乳期。\n"
    "可选：每次训练分钟、目标体重、疾病/用药、过敏、饮食偏好。\n"
    "示例：男，28岁，175cm，72kg，久坐，增肌，训练2年，每周4天，不适用孕哺，无疾病、无用药、无过敏。"
)

HELP_TEXT = (
    "我是 V1.1 饮食记录助手。\n"
    "记饮食：米饭200克，鸡胸肉150克，烹调油8克。\n"
    "包装食品：登记食物 品牌牛奶 每100克 热量250kcal 蛋白质8 脂肪9 碳水30。\n"
    "可发送：今日、本周、我的目标、修改资料、记录体重70kg、帮助。\n"
    "食物数值来自受控目录或你提供的包装标签；没有重量或数据时不会假装精确。"
)

FIELD_LABELS = {
    "age": "年龄",
    "sex": "生理性别",
    "height_cm": "身高",
    "weight_kg": "体重",
    "activity_level": "日常活动",
    "goal": "目标",
    "training_years": "训练年限",
    "training_days_per_week": "每周训练天数",
    "pregnant_or_breastfeeding": "是否孕期/哺乳期",
}
ACTIVITY_LABELS = {
    "sedentary": "久坐/低活动",
    "light": "轻活动",
    "moderate": "中等活动",
    "high": "高活动",
}
GOAL_LABELS = {"maintain": "维持", "lose": "减脂", "gain": "增肌"}


class NutritionAgent:
    """Chat workflow; all nutrition numbers come from deterministic services."""

    def __init__(
        self,
        service: NutritionService,
        deepseek: DeepSeekClient,
        profile_parser: ProfileParser | None = None,
    ):
        self.service = service
        self.deepseek = deepseek
        self.profile_parser = profile_parser or ProfileParser(deepseek)

    @staticmethod
    def _format_nutrients(prefix: str, nutrients: dict[str, float]) -> str:
        return (
            f"{prefix}{nutrients['energy_kcal']:.0f} kcal；蛋白质 {nutrients['protein_g']:.1f}g；"
            f"脂肪 {nutrients['fat_g']:.1f}g；碳水 {nutrients['carbohydrate_g']:.1f}g"
        )

    def _daily(self, user_id: str, day: datetime | None = None) -> str:
        data = self.service.get_daily_balance(user_id, local_day(day))
        lines: list[str] = []
        for period in ("breakfast", "lunch", "afternoon", "evening"):
            nutrients = data["by_meal_period"][period]
            if nutrients["energy_kcal"] > 0:
                lines.append(
                    self._format_nutrients(f"{MEAL_PERIOD_LABELS[period]}：", nutrients)
                )
        lines.append(self._format_nutrients("今日累计：", data["intake"]))
        if data["remaining"]:
            lines.append(self._format_nutrients("距今日目标：", data["remaining"]))
        lines.extend(data["notes"])
        return "\n".join(lines)

    @staticmethod
    def _profile_summary(data: dict[str, Any]) -> str:
        sex = {"male": "男", "female": "女"}.get(data.get("sex"), "未填写")
        activity = ACTIVITY_LABELS.get(data.get("activity_level"), "未填写")
        goal = GOAL_LABELS.get(data.get("goal"), "未填写")
        pregnancy = data.get("pregnant_or_breastfeeding")
        pregnancy_text = "是" if pregnancy is True else ("否" if pregnancy is False else "未填写")
        lines = [
            "请核对资料：",
            f"年龄：{data.get('age')}岁；生理性别：{sex}",
            f"身高：{data.get('height_cm')}cm；体重：{data.get('weight_kg')}kg",
            f"日常活动：{activity}；目标：{goal}",
            (
                f"训练：{data.get('training_years')}年，"
                f"每周{data.get('training_days_per_week')}天"
            ),
            f"孕期/哺乳期：{pregnancy_text}",
        ]
        if data.get("target_weight_kg") is not None:
            lines.append(f"目标体重：{data['target_weight_kg']}kg")
        for field, label in (
            ("health_conditions", "疾病/健康情况"),
            ("medications", "用药"),
            ("allergies", "过敏"),
            ("dietary_preferences", "饮食偏好"),
        ):
            values = data.get(field) or []
            if values:
                lines.append(f"{label}：{'、'.join(values)}")
        lines.append("正确请回复“确认资料”；有误直接发送更正内容。")
        return "\n".join(lines)

    @staticmethod
    def _target_summary(result: dict[str, Any]) -> str:
        targets = result["targets"]
        return (
            "资料已确认。\n"
            f"静息能量估算：{targets['resting_energy_kcal']:.0f} kcal；"
            f"PAL：{targets['physical_activity_level']:.2f}；"
            f"维持能量估算：{targets['maintenance_energy_kcal']:.0f} kcal。\n"
            f"每日初始目标：{targets['target_energy_kcal']:.0f} kcal；"
            f"蛋白质 {targets['protein_g']:.1f}g；脂肪 {targets['fat_g']:.1f}g；"
            f"碳水 {targets['carbohydrate_g']:.1f}g。\n"
            "公式为 Mifflin–St Jeor + PAL；它是起始估算，后续应结合连续体重与完整饮食记录校准。"
        )

    async def _handle_onboarding(self, user_id: str, text: str) -> str | None:
        state = self.service.get_onboarding_status(user_id)
        if state["profile_confirmed"] and state["status"] == "confirmed":
            return None
        if text == "不同意":
            return "已停止资料采集。未同意前不会保存健康资料或生成个人目标。"
        if state["status"] == "awaiting_consent":
            if text != "同意并开始":
                return CONSENT_TEXT
            self.service.begin_onboarding(user_id)
            return PROFILE_PROMPT
        if text == "同意并开始":
            return PROFILE_PROMPT
        if text == "确认资料":
            try:
                return self._target_summary(self.service.confirm_profile(user_id))
            except ValueError as exc:
                return f"暂不能确认：{exc}。请更正资料，或咨询医生/注册营养师。"

        updates = await self.profile_parser.parse(text)
        if not updates:
            missing = [FIELD_LABELS.get(field, field) for field in state["missing_fields"]]
            return f"还没有识别到资料。仍需：{'、'.join(missing)}。\n{PROFILE_PROMPT}"
        try:
            saved = self.service.record_profile_input(user_id, updates)
        except ValueError as exc:
            return f"这条资料无法保存：{exc}。请检查数值和单位。"
        if saved["missing_fields"]:
            missing = [FIELD_LABELS.get(field, field) for field in saved["missing_fields"]]
            return f"已采集本条资料。还需要：{'、'.join(missing)}。"
        return self._profile_summary(saved["data"])

    @staticmethod
    def _parse_custom_food(text: str) -> CustomFoodInput | None:
        name_match = re.search(r"(?:登记|新增)食物\s+(.+?)\s+每\s*100\s*克", text)
        if not name_match:
            return None
        name = name_match.group(1).strip()
        energy_match = re.search(
            r"(?:热量|能量)\s*(\d+(?:\.\d+)?)\s*(kcal|大卡|千卡|kj|千焦)",
            text,
            re.IGNORECASE,
        )
        patterns = {
            "protein_g": r"蛋白质?\s*(\d+(?:\.\d+)?)",
            "fat_g": r"脂肪\s*(\d+(?:\.\d+)?)",
            "carbohydrate_g": r"(?:碳水|碳水化合物)\s*(\d+(?:\.\d+)?)",
            "fiber_g": r"(?:膳食纤维|纤维)\s*(\d+(?:\.\d+)?)",
        }
        values: dict[str, float] = {}
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                values[field] = float(match.group(1))
        if not energy_match or not all(
            field in values for field in ("protein_g", "fat_g", "carbohydrate_g")
        ):
            return None
        energy = float(energy_match.group(1))
        if energy_match.group(2).lower() in {"kj", "千焦"}:
            energy /= 4.184
        fiber_known = "fiber_g" in values
        nutrients = Nutrients(
            energy_kcal=energy,
            protein_g=values["protein_g"],
            fat_g=values["fat_g"],
            carbohydrate_g=values["carbohydrate_g"],
            fiber_g=values.get("fiber_g", 0),
        )
        notes = (
            "用户提供的包装每100克营养标签"
            if fiber_known
            else "包装标签未提供膳食纤维；0表示未计入，不代表确认不含纤维"
        )
        return CustomFoodInput(name=name, nutrients_per_100g=nutrients, notes=notes)

    def _profile_target(self, user_id: str) -> str:
        profile = self.service.repository.get_profile(user_id)
        if not profile or not profile.confirmed_at:
            return "尚未确认完整资料。发送“修改资料”开始采集。"
        return (
            f"每日目标：{profile.daily_energy_kcal:.0f} kcal；"
            f"蛋白质 {profile.daily_protein_g:.1f}g；脂肪 {profile.daily_fat_g:.1f}g；"
            f"碳水 {profile.daily_carbohydrate_g:.1f}g。\n"
            f"静息能量 {profile.resting_energy_kcal:.0f} kcal；"
            f"维持能量 {profile.maintenance_energy_kcal:.0f} kcal；"
            f"公式版本：{profile.formula_version}。"
        )

    async def handle_text(
        self,
        user_id: str,
        text: str,
        message_id: str | None = None,
        eaten_at: datetime | None = None,
    ) -> str:
        normalized = text.strip()
        if normalized in {"帮助", "help", "?", "？"}:
            return HELP_TEXT
        if normalized == "删除全部数据":
            return "此操作不可恢复。如确定删除，请发送：确认删除全部数据"
        if normalized == "确认删除全部数据":
            deleted = self.service.delete_user_data(user_id)["deleted"]
            return "你的档案和饮食记录已删除。" if deleted else "没有找到可删除的数据。"
        if normalized == "修改资料":
            state = self.service.get_onboarding_status(user_id)
            if state["profile_confirmed"]:
                self.service.begin_onboarding(user_id)
                return PROFILE_PROMPT
            return CONSENT_TEXT

        onboarding_reply = await self._handle_onboarding(user_id, normalized)
        if onboarding_reply is not None:
            return onboarding_reply

        if normalized == "今日":
            return self._daily(user_id, eaten_at)
        if normalized == "本周":
            return self.service.generate_weekly_review(user_id)["review"]
        if normalized == "我的目标":
            return self._profile_target(user_id)
        if normalized == "结果":
            pending = self.service.repository.get_async_result(user_id)
            if not pending:
                return "目前没有待取的分析结果。"
            if pending["status"] == "pending":
                return "分析仍在进行中，请稍后再次发送“结果”。"
            return pending["response_text"] or "本次分析未得到可用结果，请重新发送。"

        weight_match = re.fullmatch(
            r"记录体重\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)", normalized
        )
        if weight_match:
            result = self.service.record_weight(
                user_id, float(weight_match.group(1)), measured_at=eaten_at
            )
            return f"体重已记录：{result['weight_kg']:.1f}kg。"

        if normalized.startswith(("登记食物", "新增食物")):
            custom = self._parse_custom_food(normalized)
            if not custom:
                return (
                    "请按包装每100克登记，例如：登记食物 品牌巧克力 每100克 "
                    "热量550kcal 蛋白质7 脂肪35 碳水55 纤维5。"
                )
            saved = self.service.register_custom_food(user_id, custom.model_dump())
            food = saved["food"]
            return self._format_nutrients(
                f"已登记“{food['name']}”每100克：", food["nutrients_per_100g"]
            )

        custom_foods = self.service.repository.list_custom_foods(user_id)
        if (
            "巧克力" in normalized
            and "牛奶巧克力" not in normalized
            and "黑巧克力" not in normalized
            and not any(food.name in normalized for food in custom_foods)
        ):
            self.service.repository.record_unknown_food(user_id, "巧克力", normalized)
            return (
                "“巧克力”种类和品牌差异较大。请改发“牛奶巧克力10克”或"
                "“黑巧克力10克”；若是包装食品，请发送包装每100克的热量、蛋白质、脂肪和碳水进行登记。"
            )

        custom_names = [food.name for food in custom_foods]
        parsed = await self.service.parser.parse(normalized, custom_names)
        if not parsed.items:
            return (
                "我还不能可靠识别这条饮食记录。请写明食物和克数，例如："
                "米饭200克，鸡胸肉150克，烹调油8克。"
            )
        missing = [item.name for item in parsed.items if item.grams is None]
        if missing:
            return f"还需要这些食物的克数：{'、'.join(missing)}。没有重量时不会输出伪精确热量。"

        custom_by_name = {
            self.service.catalog._normalize(name): food
            for food in custom_foods
            for name in {food.name, *food.aliases}
        }
        inputs: list[MealItemInput] = []
        unresolved: list[str] = []
        for item in parsed.items:
            food = self.service.catalog.exact(item.name)
            if not food:
                food = custom_by_name.get(self.service.catalog._normalize(item.name))
            if not food:
                unresolved.append(item.name)
                self.service.repository.record_unknown_food(user_id, item.name, normalized)
                continue
            inputs.append(
                MealItemInput(
                    food_id=food.id,
                    grams=item.grams,
                    cooking_method=item.cooking_method,
                )
            )
        if unresolved:
            if any(name in {"巧克力", "巧克力制品"} for name in unresolved):
                return (
                    "“巧克力”种类和品牌差异较大。请改发“牛奶巧克力10克”或"
                    "“黑巧克力10克”；若是包装食品，请发送包装每100克的热量、蛋白质、脂肪和碳水进行登记。"
                )
            return (
                f"尚未收录：{'、'.join(unresolved)}。我已记下补库请求，但不会编造营养数字。"
                "可发送“登记食物 名称 每100克 热量… 蛋白质… 脂肪… 碳水…”。"
            )

        saved = self.service.save_meal(
            user_id,
            inputs,
            eaten_at=eaten_at,
            note=normalized,
            source_message_id=message_id,
        )
        calculation = saved["calculation"]
        day = local_day(eaten_at)
        daily = self.service.get_daily_balance(user_id, day)
        period = saved["meal_period"]
        lines = [
            self._format_nutrients(
                f"已记为{MEAL_PERIOD_LABELS[period]}，本餐：", calculation["totals"]
            ),
            self._format_nutrients("今日累计：", daily["intake"]),
        ]
        if daily["remaining"]:
            lines.append(self._format_nutrients("距今日目标：", daily["remaining"]))
        if calculation["warnings"]:
            lines.append(calculation["warnings"][0])
        return "\n".join(lines)
