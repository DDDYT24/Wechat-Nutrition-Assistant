from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .deepseek import DeepSeekClient
from .emotions import detect_emotion
from .exercise import ExerciseService
from .models import CustomFoodInput, MealItemInput, Nutrients
from .profile_parser import ProfileParser
from .service import NutritionService
from .supplements import resolve_supplement_grams
from .time_utils import MEAL_PERIOD_LABELS, local_day

CONSENT_TEXT = (
    "欢迎使用微信营养记录助手 V1.2。\n"
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
    "我是 V1.2 饮食记录助手。\n"
    "记饮食：米饭200克，鸡胸肉150克，烹调油8克。\n"
    "也可用碗/个/杯等份量：一碗米饭，一个鸡蛋，一杯牛奶。\n"
    "模糊份量也支持：几口米饭、半碗面条、大半份盖浇饭。\n"
    "记训练：练胸和三头，90分钟 · 今日步数12000。\n"
    "补充剂：蛋白粉一勺、肌酸5克、鱼油2粒。\n"
    "包装食品：登记食物 品牌名 每100克 热量… 蛋白质… 脂肪… 碳水…\n"
    "可发送：今日、今日总结、本周、体重趋势、我的目标、修改资料、体重72kg、帮助。\n"
    "食物数值优先使用中国食物成分表第6版或包装标签；未收录食物会调用大模型估算并明确标注。\n"
    "也可以直接问今天还能吃多少或下一餐吃什么。"
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
    """Chat workflow with catalog calculations and explicit LLM estimates."""

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

    @staticmethod
    def _is_nutrition_question(text: str) -> bool:
        return bool(
            re.search(
                r"(?:还(?:能|可以)吃多少|今日.*(?:剩余|还可以吃)|"
                r"帮我算.*(?:热量|卡路里)|接下来吃什么|下一餐吃什么|"
                r"建议我?(?:接下来|下一餐|今天)?吃什么|怎么吃|如何搭配)",
                text,
            )
        )

    async def _answer_nutrition_question(
        self, user_id: str, text: str, at: datetime | None
    ) -> str:
        daily = self.service.get_daily_balance(user_id, local_day(at))
        profile = self.service.repository.get_profile(user_id)
        if self.deepseek.enabled and hasattr(self.deepseek, "answer_nutrition_question"):
            try:
                answer = await self.deepseek.answer_nutrition_question(
                    text,
                    daily,
                    profile.model_dump(mode="json") if profile else None,
                )
                if answer:
                    return answer
            except Exception:
                pass
        remaining = daily.get("remaining")
        if remaining:
            kcal = remaining["energy_kcal"]
            suggestion = (
                "可以优先选择一份瘦肉或豆制品配蔬菜和适量主食。"
                if kcal >= 500
                else "可以选择无糖酸奶、水果、鸡蛋或少量坚果，注意控制份量。"
            )
            return f"今天还可摄入约 {kcal:.0f} kcal。{suggestion}"
        return self._daily(user_id, at) + "\n下一餐优先保证蛋白质和蔬菜，再按饥饿程度补充主食。"

    async def _estimate_foods(
        self, user_id: str, text: str, names: list[str]
    ) -> dict[str, tuple[MealItemInput, object]]:
        if not names or not self.deepseek.enabled or not hasattr(self.deepseek, "estimate_foods"):
            return {}
        try:
            result = await self.deepseek.estimate_foods(text, names)
        except Exception:
            return {}
        estimates: dict[str, tuple[MealItemInput, object]] = {}
        for item in result.items:
            notes = f"大模型估算，置信度 {item.confidence:.0%}"
            if item.assumptions:
                notes += f"；{item.assumptions}"
            saved = self.service.register_custom_food(
                user_id,
                CustomFoodInput(
                    name=item.name,
                    nutrients_per_100g=item.nutrients_per_100g,
                    notes=notes,
                    origin="llm_estimate",
                ),
            )["food"]
            estimates[self.service.catalog._normalize(item.name)] = (
                MealItemInput(food_id=saved["id"], grams=item.grams),
                item,
            )
        return estimates

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

        # ── V1.2: emotion detection (before any other processing) ──
        emotion = detect_emotion(normalized)
        if emotion and emotion.should_block_meal_parsing:
            return emotion.response
            # For non-blocking emotions, note it and continue to normal processing.
            # The tone can be stored for context (future: user_memory.py).

        # Detect training early, but persist it only after onboarding and command handling.
        training_session = ExerciseService.parse_training_text(normalized)
        training_reply: str | None = None

        # ── V1.2: supplement detection (no profile required) ──
        _cn_digits = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
                       "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        _cn_num_pat = r"(?:一|两|二|三|四|五|六|七|八|九|十|\d+(?:\.\d+)?)"
        supp_match = re.match(
            rf"(.+?)\s*({_cn_num_pat})\s*(勺|粒|颗|片|克|g)",
            normalized,
        )
        if supp_match:
            supp_name = supp_match.group(1).strip()
            raw_num = supp_match.group(2)
            supp_amount = float(_cn_digits.get(raw_num, raw_num))
            supp_unit = supp_match.group(3)
            supp_result = resolve_supplement_grams(supp_name, supp_amount, supp_unit)
            if supp_result:
                supp_grams, supp_kcal, supp_note = supp_result
                return (
                    f"已记录补充剂：{supp_name} {supp_amount:.0f}{supp_unit}\n"
                    f"  约 {supp_grams:.0f}g · {supp_kcal} kcal\n"
                    + (f"  💡 {supp_note}" if supp_note else "")
                )

        onboarding_reply = await self._handle_onboarding(user_id, normalized)
        if onboarding_reply is not None:
            return onboarding_reply

        if self._is_nutrition_question(normalized):
            return await self._answer_nutrition_question(user_id, normalized, eaten_at)

        if normalized == "今日":
            return self._daily(user_id, eaten_at)
        if normalized == "本周":
            return self.service.generate_weekly_review(user_id)["review"]
        if normalized == "我的目标":
            return self._profile_target(user_id)
        if normalized in {"今日总结", "日报", "今日报告"}:
            from .daily_summary import generate_daily_summary
            summary = generate_daily_summary(self.service, user_id)
            if summary:
                return summary
            return "今天还没有饮食记录，无法生成日报。发送「帮助」查看如何记录。"
        if normalized in {"体重趋势", "体重"}:
            trend = self.service.get_weight_trend(user_id)
            if not trend["records"]:
                return '还没有体重记录。发送「体重72kg」开始记录。'
            lines = [f"最近 {trend['count']} 条体重记录："]
            for r in trend["records"][-7:]:
                lines.append(f"  {r['measured_at'][:10]}  {r['weight_kg']}kg")
            if trend["change_kg"] is not None:
                if trend["change_kg"] < 0:
                    direction = "↓"
                elif trend["change_kg"] > 0:
                    direction = "↑"
                else:
                    direction = "→"
                lines.append(f"变化：{direction} {trend['change_kg']:+.1f}kg")
            if trend["ready_for_target_calibration"]:
                lines.append("💡 已有足够数据，可以考虑校准目标。")
            return "\n".join(lines)
        if normalized == "结果":
            pending = self.service.repository.get_async_result(user_id)
            if not pending:
                return "目前没有待取的分析结果。"
            if pending["status"] == "pending":
                return "分析仍在进行中，请稍后再次发送“结果”。"
            return pending["response_text"] or "本次分析未得到可用结果，请重新发送。"

        weight_match = re.fullmatch(
            r"(?:记录)?\s*体重\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)?", normalized
        )
        if weight_match:
            result = self.service.record_weight(
                user_id, float(weight_match.group(1)), measured_at=eaten_at
            )
            return f"体重已记录：{result['weight_kg']:.1f}kg。发送“体重趋势”查看变化。"
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
        controlled_names = [food.name for food in self.service.catalog.foods]
        controlled_names.extend(food.name for food in custom_foods)
        intent_plan = None
        if self.deepseek.enabled and hasattr(self.deepseek, "parse_intents"):
            try:
                intent_plan = await self.deepseek.parse_intents(normalized, controlled_names)
            except Exception:
                intent_plan = None
        if (
            intent_plan
            and "query" in intent_plan.intent_types
            and not intent_plan.meal_items
            and not intent_plan.exercise
        ):
            return await self._answer_nutrition_question(user_id, normalized, eaten_at)

        estimate_names = []
        if intent_plan:
            estimate_names = [
                item.raw_name
                for item in intent_plan.meal_items
                if item.needs_clarification or not item.catalog_name
            ]
        estimated = await self._estimate_foods(user_id, normalized, estimate_names)
        if intent_plan and intent_plan.exercise and not training_session:
            training_session = ExerciseService.from_structured(
                intent_plan.exercise,
                intent_plan.exercise_text or normalized,
            )

        if training_session and (training_session.duration_minutes > 0 or training_session.steps):
            self.service.record_exercise(
                user_id,
                training_session,
                exercised_at=eaten_at,
                source_message_id=message_id,
            )
            profile = self.service.repository.get_profile(user_id)
            weight = profile.weight_kg if profile else None
            training_reply = ExerciseService.format_session_reply(training_session, weight)

        custom_foods = self.service.repository.list_custom_foods(user_id)
        custom_names = [food.name for food in custom_foods]
        meal_text = intent_plan.meal_text if intent_plan and intent_plan.meal_text else normalized
        parsed = await self.service.parser.parse(meal_text, custom_names)
        if not parsed.items and not estimated:
            if training_reply:
                return training_reply
            meal_reply = (
                "我还不能可靠识别这条饮食记录。请写明食物和份量，例如：\n"
                "• 米饭200克，鸡胸肉150克，烹调油8克\n"
                "• 一碗米饭，一个鸡蛋，一杯豆浆\n"
                "• 若是包装食品（如品牌欧包），可先登记：\n"
                "  登记食物 名称 每100克 热量… 蛋白质… 脂肪… 碳水…"
            )
            return self._join_replies(meal_reply, training_reply)
        missing = [
            item.name
            for item in parsed.items
            if item.grams is None
            and self.service.catalog._normalize(item.name) not in estimated
        ]
        if missing:
            meal_reply = (
                f"还需要这些食物的份量：{'、'.join(missing)}。\n"
                "可以写克数（200克），也可以用碗/个/杯等（一碗、一个、一杯）。\n"
                "没有重量时不会输出伪精确热量。"
            )
            return self._join_replies(meal_reply, training_reply)

        custom_by_name = {
            self.service.catalog._normalize(name): food
            for food in custom_foods
            for name in {food.name, *food.aliases}
        }
        inputs: list[MealItemInput] = []
        unresolved: list[str] = []
        for item in parsed.items:
            normalized_name = self.service.catalog._normalize(item.name)
            if normalized_name in estimated:
                continue
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
        for estimated_input, _estimate in estimated.values():
            inputs.append(estimated_input)
        if unresolved:
            late_estimated = await self._estimate_foods(user_id, normalized, unresolved)
            for estimated_input, _estimate in late_estimated.values():
                inputs.append(estimated_input)
            unresolved = [
                name
                for name in unresolved
                if self.service.catalog._normalize(name) not in late_estimated
            ]
            estimated.update(late_estimated)
        if unresolved:
            return self._join_replies(
                f"模型暂时没有返回可用的营养估算：{'、'.join(unresolved)}。请稍后重试。",
                training_reply,
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
        # Build a compact item list
        item_lines: list[str] = []
        low_confidence_items: list[str] = []
        composite_prompts: list[str] = []
        for item in parsed.items:
            food = self.service.catalog.exact(item.name)
            alias_match = next(
                (f" ({n})" for n, f in self.service.catalog.all_aliases()
                 if f and f.name == item.name and n != item.name),
                "",
            )
            if item.grams:
                item_lines.append(f"  {item.name}{alias_match} {item.grams:.0f}g")
            if item.confidence < 0.6:
                low_confidence_items.append(item.name)
            if item.brand and item.brand.startswith("⚠"):
                composite_prompts.append(item.brand[1:])
        for _estimated_input, estimate in estimated.values():
            item_lines.append(f"  {estimate.name} ≈{estimate.grams:.0f}g（大模型估算）")

        lines = [
            f"{MEAL_PERIOD_LABELS[period]}已记录",
            "\n".join(item_lines) if item_lines else normalized,
            "",
            self._format_nutrients("本餐：", calculation["totals"]),
            self._format_nutrients("今日累计：", daily["intake"]),
        ]
        if daily["remaining"]:
            lines.append(self._format_nutrients("距今日目标：", daily["remaining"]))
        if low_confidence_items:
            lines.append(
                f"\n⚠️ {'、'.join(low_confidence_items)} 使用默认份量估算，实际可能有 ±20-30% 偏差"
            )
        if composite_prompts:
            lines.append(f"\n💡 {composite_prompts[0]}")
        if calculation["warnings"]:
            lines.append(f"\n⚠ {calculation['warnings'][0]}")
        return self._join_replies("\n".join(lines), training_reply)

    @staticmethod
    def _join_replies(*replies: str | None) -> str:
        return "\n\n".join(reply for reply in replies if reply)
