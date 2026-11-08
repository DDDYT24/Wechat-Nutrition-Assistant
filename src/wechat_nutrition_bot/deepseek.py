from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .models import (
    DailyBalance,
    EstimatedMealResult,
    MealCalculation,
    MealParseResult,
    ProfileDraftData,
    StructuredIntentResult,
)


class DeepSeekClient:
    """Small, replaceable adapter for DeepSeek's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ):
        self.enabled = bool(api_key)
        self.model = model
        self.client = (
            AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
            if self.enabled
            else None
        )

    async def parse_meal(self, text: str, allowed_food_names: list[str]) -> MealParseResult:
        if not self.client:
            raise RuntimeError("DeepSeek API is not configured")
        system = (
            "你是饮食记录结构化解析器。只提取用户明确说出的食物、克数、品牌和烹饪方式。"
            "不得估算碗、份、个的克数，不得计算热量，不得补写用户没有提供的数据。"
            "只输出 JSON：{items:[{name,grams,cooking_method,brand,confidence}],"
            "missing_fields:[],notes:[]}。grams 未明确时必须为 null；"
            "confidence 必须是 0 到 1 的数字，不得使用 high、medium、low 等文字。"
            f"受控食物名称与别名如下：{allowed_food_names}。不在列表中的食物仍可保留名称，"
            "但不要生成任何营养数据。"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=700,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        payload["parser"] = "deepseek"
        return MealParseResult.model_validate(payload)

    async def explain_meal(
        self, calculation: MealCalculation, daily_balance: DailyBalance | None = None
    ) -> str:
        if not self.client:
            raise RuntimeError("DeepSeek API is not configured")

        def display_nutrients(nutrients: Any) -> dict[str, float | int]:
            return {
                "energy_kcal": round(nutrients.energy_kcal),
                "protein_g": round(nutrients.protein_g, 1),
                "fat_g": round(nutrients.fat_g, 1),
                "carbohydrate_g": round(nutrients.carbohydrate_g, 1),
                "fiber_g": round(nutrients.fiber_g, 1),
            }

        payload: dict[str, Any] = {
            "meal": {
                "status": calculation.status,
                "items": [
                    {
                        "food_name": item.food_name,
                        "grams": item.grams,
                        "data_status": item.data_status,
                    }
                    for item in calculation.items
                ],
                "totals": display_nutrients(calculation.totals),
                "warnings": calculation.warnings,
            }
        }
        if daily_balance:
            payload["daily_balance"] = {
                "meal_count": daily_balance.meal_count,
                "intake": display_nutrients(daily_balance.intake),
                "targets": (
                    display_nutrients(daily_balance.targets) if daily_balance.targets else None
                ),
                "remaining": (
                    display_nutrients(daily_balance.remaining) if daily_balance.remaining else None
                ),
                "notes": daily_balance.notes,
            }
        system = (
            "你是面向一般健康成年人的饮食记录助手。只能使用用户提供的结构化 JSON 数字，"
            "禁止创造、修改或推测任何热量和营养素数值。先简明复述本餐结果，再给1到2条温和、"
            "可执行的普通健康饮食建议。若数据状态为 seed、partial 或存在 warnings，必须明确说明"
            "结果仍需核验。不得诊断疾病、提供治疗性饮食或调整药物。输出纯文本，不使用表格。"
            "禁止使用 Markdown 标记，包括星号、井号、反引号和 Markdown 标题。"
            "能量显示为 JSON 中给出的整数 kcal，其他营养素显示到一位小数。"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=500,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        text = (response.choices[0].message.content or "").strip()
        return text.replace("**", "").replace("__", "").replace("`", "")

    async def parse_profile(self, text: str) -> dict[str, Any]:
        """Extract only explicitly stated onboarding fields; never derive targets here."""
        if not self.client:
            raise RuntimeError("DeepSeek API is not configured")
        system = (
            "你是健康资料结构化解析器。只提取用户本条消息明确说出的值，不推测、不计算。"
            "字段：age整数；sex只能是male或female且指用于能量方程的生理性别；"
            "height_cm；weight_kg；activity_level只能是sedentary/light/moderate/high；"
            "goal只能是maintain/lose/gain；training_years；training_days_per_week；"
            "training_minutes_per_session；target_weight_kg；pregnant_or_breastfeeding布尔值；"
            "health_conditions、medications、allergies、dietary_preferences为字符串数组；notes。"
            "如果用户说无疾病、无用药或无过敏，对应数组应为空。"
            "没有明确提到的字段不得出现在provided_fields中。"
            "只输出JSON：{updates:{},provided_fields:[]}，不得输出目标热量或营养素。"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=700,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        updates = payload.get("updates") or {}
        provided = {
            field
            for field in payload.get("provided_fields", [])
            if field in ProfileDraftData.model_fields
        }
        validated = ProfileDraftData.model_validate(updates)
        return validated.model_dump(include=provided)

    async def classify_intent(self, text: str) -> dict[str, Any]:
        """V1.2: classify user intent before parsing. Returns structured intent + extracted data."""
        if not self.client:
            return {
                "intent": "meal_record", "confidence": 0.5,
                "notes": ["DeepSeek未配置，默认按饮食记录处理"],
            }
        system = (
            "你是用户意图分类器。分析用户消息，判断主要意图。"
            "意图类型：meal_record(记录饮食)、training(训练/运动/步数)、"
            "query(查询数据/今日/本周/目标)、emotion(情绪表达/抱怨/焦虑/暴食)、"
            "profile(修改资料/设置)、other(其他)。"
            "同时提取相关结构化信息："
            "- 训练: type(力量/有氧/HIIT/柔韧/其他), duration_minutes, intensity(低/中/高), "
            "  body_part, steps(步数), exercises(具体动作列表)"
            "- 情绪: tone(positive/negative/neutral/anxious/guilty), "
            "  keywords(提取的情绪关键词列表)"
            "- 查询: query_type(today/week/goal/weight_trend/help)"
            "只输出JSON: {intent, confidence, extracted:{...}, notes:[]}。"
            "不要编造不在消息中的数据。"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=400,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        return {
            "intent": payload.get("intent", "meal_record"),
            "confidence": payload.get("confidence", 0.5),
            "extracted": payload.get("extracted", {}),
            "notes": payload.get("notes", []),
        }

    async def parse_intents(
        self, text: str, allowed_food_names: list[str]
    ) -> StructuredIntentResult:
        """Split a message into strict language-only intents; never accept nutrition totals."""
        if not self.client:
            raise RuntimeError("DeepSeek API is not configured")
        system = (
            "你是多意图健康记录结构化解析器。把一条消息中的饮食和训练同时提取，"
            "只输出JSON，不输出解释。intent_types可包含meal_record、training、query、"
            "emotion、profile、other。meal_text和exercise_text必须逐字复制用户原文中的对应片段。"
            "meal_items字段只能包含raw_name、catalog_name、amount、unit、explicit_grams、"
            "cooking_method、needs_clarification。catalog_name只能精确选择受控目录标准名；"
            "泛称对应多个具体品种且没有代表值时必须为null并设置needs_clarification=true。"
            "只有用户明确说出克数时才能填写explicit_grams；碗、个、份等不能由你换算克数。"
            "exercise字段只能包含type、duration_minutes、intensity、body_parts、exercises、steps。"
            "严禁输出热量、蛋白质、脂肪、碳水、消耗、目标、累计值或任何其他字段。"
            "输出格式：{intent_types:[],meal_text:null,meal_items:[],exercise_text:null,"
            "exercise:null,notes:[]}。"
            f"受控目录标准名：{allowed_food_names}"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=900,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        payload["parser"] = "deepseek"
        result = StructuredIntentResult.model_validate(payload)
        allowed = set(allowed_food_names)
        for item in result.meal_items:
            if item.catalog_name and item.catalog_name not in allowed:
                item.catalog_name = None
                item.needs_clarification = True
                result.notes.append(f"目录中未找到：{item.raw_name}")
        if result.meal_text and result.meal_text not in text:
            result.meal_text = None
            result.notes.append("模型饮食片段不是原文子串，已忽略")
        if result.exercise_text and result.exercise_text not in text:
            result.exercise_text = None
            result.notes.append("模型训练片段不是原文子串，已忽略")
        return result

    async def estimate_foods(
        self, text: str, unresolved_names: list[str]
    ) -> EstimatedMealResult:
        """Estimate unresolved foods from common portions and recipes."""
        if not self.client:
            raise RuntimeError("DeepSeek API is not configured")
        requested = list(dict.fromkeys(name.strip() for name in unresolved_names if name.strip()))
        system = (
            "你是一般健康成人饮食记录的营养估算器。用户的食物不在本地数据库时，"
            "根据常见中国食物份量、常见配方和烹饪方式给出最合理的估算，不要拒绝回答。"
            "name必须逐字使用待估算名称；grams是本次实际食用量估算；nutrients_per_100g"
            "包含energy_kcal、protein_g、fat_g、carbohydrate_g、fiber_g。"
            "confidence为0到1，assumptions简述主要份量或配方假设。"
            "不要输出每日目标、今日累计或运动消耗。只输出JSON："
            "{items:[{name,grams,nutrients_per_100g:{energy_kcal,protein_g,fat_g,"
            "carbohydrate_g,fiber_g},confidence,assumptions}],notes:[]}。"
            f"待估算名称：{requested}"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1000,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        result = EstimatedMealResult.model_validate_json(
            response.choices[0].message.content or "{}"
        )
        allowed = set(requested)
        result.items = [item for item in result.items if item.name in allowed]
        return result

    async def answer_nutrition_question(
        self,
        text: str,
        daily_balance: dict[str, Any],
        profile: dict[str, Any] | None,
    ) -> str:
        """Answer remaining-calorie and next-meal questions from saved daily context."""
        if not self.client:
            raise RuntimeError("DeepSeek API is not configured")
        context = {"question": text, "daily_balance": daily_balance, "profile": profile}
        system = (
            "你是一般健康成人的饮食助手。直接回答用户关于今日还能吃多少、下一餐吃什么、"
            "如何搭配等问题，不要说不会。daily_balance中的已摄入、目标和剩余值来自数据库，"
            "必须原样使用；可以推理并给出1到3个具体食物或餐食方案，方案热量和营养可以合理估算，"
            "但必须称为估算。考虑profile中的目标、过敏和饮食偏好。不要诊断、治疗疾病或调整药物。"
            "输出简洁中文纯文本，不使用Markdown表格。"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            temperature=0.3,
            max_tokens=700,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return (response.choices[0].message.content or "").strip()
