from __future__ import annotations

import re
from typing import Any

from .deepseek import DeepSeekClient


class ProfileParser:
    """Rules first, then DeepSeek only for explicitly stated fields rules did not capture."""

    def __init__(self, deepseek: DeepSeekClient):
        self.deepseek = deepseek

    @staticmethod
    def _number(text: str, patterns: list[str]) -> float | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def parse_rules(self, text: str) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        age = self._number(text, [r"(?:年龄|年纪)\s*[:：]?\s*(\d{1,3})", r"(\d{1,3})\s*岁"])
        if age is not None:
            updates["age"] = int(age)

        if re.search(
            r"(?:生理性别|性别)\s*[:：]?\s*(?:男|男性)|(?:^|[，,；;\s])男(?:性|生)?(?:$|[，,；;\s])",
            text,
        ):
            updates["sex"] = "male"
        elif re.search(
            r"(?:生理性别|性别)\s*[:：]?\s*(?:女|女性)|(?:^|[，,；;\s])女(?:性|生)?(?:$|[，,；;\s])",
            text,
        ):
            updates["sex"] = "female"

        height = self._number(
            text,
            [r"身高\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)?", r"(\d{3})\s*(?:cm|厘米)"],
        )
        if height is not None:
            updates["height_cm"] = height

        target_weight = self._number(
            text,
            [r"目标体重\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)"],
        )
        if target_weight is not None:
            updates["target_weight_kg"] = target_weight
        weight_text = re.sub(r"目标体重[^，,。；;\n]*", "", text)
        weight = self._number(
            weight_text,
            [
                r"(?:当前)?体重\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)",
                r"(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)",
            ],
        )
        if weight is not None:
            updates["weight_kg"] = weight

        training_years = self._number(
            text,
            [r"(?:训练|健身)(?:年限|经验)?\s*[:：]?\s*(\d+(?:\.\d+)?)\s*年"],
        )
        if training_years is not None:
            updates["training_years"] = training_years
        elif re.search(r"(?:没|无|零|0)\s*(?:训练|健身)(?:经验)?|刚开始训练", text):
            updates["training_years"] = 0

        days = self._number(
            text,
            [r"(?:每周|一周)\s*(?:训练|健身)?\s*(\d)\s*天", r"周练\s*(\d)"],
        )
        if days is not None:
            updates["training_days_per_week"] = int(days)
        minutes = self._number(
            text,
            [r"(?:每次|单次)\s*(?:训练)?\s*(\d+)\s*分钟"],
        )
        if minutes is not None:
            updates["training_minutes_per_session"] = int(minutes)

        if any(term in text for term in ("久坐", "办公室久坐", "低活动", "很少走动")):
            updates["activity_level"] = "sedentary"
        elif any(term in text for term in ("轻活动", "轻度活动", "偶尔走动")):
            updates["activity_level"] = "light"
        elif any(term in text for term in ("中等活动", "中度活动", "经常走动", "站立工作")):
            updates["activity_level"] = "moderate"
        elif any(term in text for term in ("高活动", "重体力", "体力劳动", "非常活跃")):
            updates["activity_level"] = "high"

        if any(term in text for term in ("减脂", "减重", "减肥")):
            updates["goal"] = "lose"
        elif any(term in text for term in ("增肌", "增重")):
            updates["goal"] = "gain"
        elif any(term in text for term in ("维持", "保持体重")):
            updates["goal"] = "maintain"

        if any(term in text for term in ("怀孕", "孕期", "哺乳期", "母乳喂养")) and not any(
            term in text for term in ("未怀孕", "没有怀孕", "非孕期", "不在孕期", "不哺乳")
        ):
            updates["pregnant_or_breastfeeding"] = True
        elif any(
            term in text
            for term in ("未怀孕", "没有怀孕", "非孕期", "不在孕期", "不哺乳", "不适用孕哺")
        ) or updates.get("sex") == "male":
            updates["pregnant_or_breastfeeding"] = False

        list_fields = {
            "health_conditions": ("疾病", "病史", "健康情况"),
            "medications": ("用药", "药物"),
            "allergies": ("过敏",),
            "dietary_preferences": ("饮食偏好", "忌口", "素食"),
        }
        for field, labels in list_fields.items():
            label_pattern = "|".join(map(re.escape, labels))
            if re.search(rf"(?:无|没有|暂无)(?:{label_pattern})", text):
                updates[field] = []
                continue
            match = re.search(
                rf"(?:{label_pattern})\s*[:：]?\s*([^，,。；;\n]+)", text, re.IGNORECASE
            )
            if match:
                value = match.group(1).strip()
                updates[field] = [] if value in {"无", "没有", "否", "暂无"} else [value]
        return updates

    async def parse(self, text: str) -> dict[str, Any]:
        rules = self.parse_rules(text)
        if rules:
            return rules
        if not self.deepseek.enabled:
            return rules
        try:
            model = await self.deepseek.parse_profile(text)
        except Exception:
            return rules
        return {**model, **rules}
