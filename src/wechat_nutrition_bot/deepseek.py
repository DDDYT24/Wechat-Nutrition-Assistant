from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .models import DailyBalance, MealCalculation, MealParseResult, ProfileDraftData


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
            return {"intent": "meal_record", "confidence": 0.5, "notes": ["DeepSeek未配置，默认按饮食记录处理"]}
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
