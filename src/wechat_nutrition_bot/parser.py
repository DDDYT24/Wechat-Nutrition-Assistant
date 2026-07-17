from __future__ import annotations

import re

from .catalog import FoodCatalog
from .deepseek import DeepSeekClient
from .models import MealParseResult, ParsedMealItem

COOKING_METHODS = ["清蒸", "水煮", "煮", "炒", "煎", "炸", "烤", "炖", "焖", "凉拌"]
UNIT_FACTORS = {"g": 1.0, "克": 1.0, "kg": 1000.0, "公斤": 1000.0, "千克": 1000.0}


class MealParser:
    """Parse explicit gram-based inputs first, then optionally ask DeepSeek for structure."""

    def __init__(self, catalog: FoodCatalog, deepseek: DeepSeekClient):
        self.catalog = catalog
        self.deepseek = deepseek

    @staticmethod
    def _method_near(text: str, start: int, end: int) -> str | None:
        nearby = text[max(0, start - 6) : min(len(text), end + 6)]
        return next((method for method in COOKING_METHODS if method in nearby), None)

    def parse_rules(
        self, text: str, additional_food_names: list[str] | None = None
    ) -> MealParseResult:
        items: list[ParsedMealItem] = []
        seen: set[str] = set()
        for alias, food in self.catalog.all_aliases():
            if food.id in seen:
                continue
            escaped = re.escape(alias)
            after = re.search(
                rf"{escaped}\s*(?:约|大约|差不多)?\s*(\d+(?:\.\d+)?)\s*(kg|公斤|千克|g|克)",
                text,
                re.IGNORECASE,
            )
            before = re.search(
                rf"(?:约|大约|差不多)?\s*(\d+(?:\.\d+)?)\s*(kg|公斤|千克|g|克)\s*(?:的)?\s*{escaped}",
                text,
                re.IGNORECASE,
            )
            plain = re.search(escaped, text, re.IGNORECASE)
            match = after or before or plain
            if not match:
                continue
            grams = None
            if match is after or match is before:
                grams = float(match.group(1)) * UNIT_FACTORS[match.group(2).lower()]
            items.append(
                ParsedMealItem(
                    name=food.name,
                    grams=grams,
                    cooking_method=self._method_near(text, match.start(), match.end()),
                    confidence=1.0 if grams is not None else 0.8,
                )
            )
            seen.add(food.id)

        for name in sorted(set(additional_food_names or []), key=len, reverse=True):
            marker = f"custom:{name}"
            if marker in seen:
                continue
            escaped = re.escape(name)
            after = re.search(
                rf"{escaped}\s*(?:约|大约|差不多)?\s*(\d+(?:\.\d+)?)\s*"
                r"(kg|公斤|千克|g|克)",
                text,
                re.IGNORECASE,
            )
            before = re.search(
                rf"(?:约|大约|差不多)?\s*(\d+(?:\.\d+)?)\s*"
                rf"(kg|公斤|千克|g|克)\s*(?:的)?\s*{escaped}",
                text,
                re.IGNORECASE,
            )
            plain = re.search(escaped, text, re.IGNORECASE)
            match = after or before or plain
            if not match:
                continue
            grams = None
            if match is after or match is before:
                grams = float(match.group(1)) * UNIT_FACTORS[match.group(2).lower()]
            items.append(
                ParsedMealItem(
                    name=name,
                    grams=grams,
                    cooking_method=self._method_near(text, match.start(), match.end()),
                    confidence=1.0 if grams is not None else 0.8,
                )
            )
            seen.add(marker)

        missing: list[str] = []
        if not items:
            missing.append("可识别的食物名称")
        elif any(item.grams is None for item in items):
            missing.append("每种食物的克数")
        return MealParseResult(items=items, missing_fields=missing, parser="rules")

    async def parse(
        self, text: str, additional_food_names: list[str] | None = None
    ) -> MealParseResult:
        rules = self.parse_rules(text, additional_food_names)
        if rules.items and not rules.missing_fields:
            return rules
        if not self.deepseek.enabled:
            return rules
        allowed_names = sorted(
            {name for name, _ in self.catalog.all_aliases()} | set(additional_food_names or [])
        )
        try:
            model_result = await self.deepseek.parse_meal(text, allowed_names)
        except Exception:
            rules.notes.append("DeepSeek 暂时不可用，已降级为规则解析")
            return rules
        if rules.items and model_result.items:
            # Prefer explicit rule-derived grams; use the model only to enrich or discover names.
            merged = {item.name: item for item in model_result.items}
            for item in rules.items:
                merged[item.name] = item
            result = MealParseResult(
                items=list(merged.values()),
                missing_fields=[],
                parser="hybrid",
                notes=model_result.notes,
            )
            if any(item.grams is None for item in result.items):
                result.missing_fields.append("每种食物的克数")
            return result
        return model_result
