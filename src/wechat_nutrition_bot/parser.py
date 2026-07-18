"""V1.2 meal parser with natural-unit, vague-quantifier, and composite-food support.

Rules-first hybrid: regex matches explicit gram inputs and natural units first,
then optionally enriches results with DeepSeek for ambiguous expressions.
"""

from __future__ import annotations

import re

from .catalog import FoodCatalog
from .deepseek import DeepSeekClient
from .models import MealParseResult, ParsedMealItem
from .portions import (
    COMPOSITE_FOODS,
    VAGUE_QUANTIFIERS,
    PortionResolver,
    _normalize as p_normalize,
)

COOKING_METHODS = ["清蒸", "水煮", "煮", "炒", "煎", "炸", "烤", "炖", "焖", "凉拌", "红烧", "卤"]
GRAM_UNITS = r"(kg|公斤|千克|g|克)"
GRAM_FACTORS = {"g": 1.0, "克": 1.0, "kg": 1000.0, "公斤": 1000.0, "千克": 1000.0}
NATURAL_UNITS = r"(个|碗|杯|片|颗|粒|勺|块|根|包|瓶|盒|份|把|罐|听|盘|笼|屉)"

# Chinese numerals → integer mapping for regex patterns
_CN_NUMERAL_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "两": 2, "几": None,  # "几" = vague, handled separately
}
# Build regex alternation: (?:一|两|二|三|四|五|六|七|八|九|十|\d+(?:\.\d+)?)
_CN_NUMERAL_PAT = "|".join(_CN_NUMERAL_MAP)
_NUMBER_PAT = rf"({_CN_NUMERAL_PAT}|\d+(?:\.\d+)?)"

GRAM_FACTORS = {"g": 1.0, "克": 1.0, "kg": 1000.0, "公斤": 1000.0, "千克": 1000.0}


class MealParser:
    """Parse explicit gram-based inputs first, natural units second, then optionally ask DeepSeek."""

    def __init__(self, catalog: FoodCatalog, deepseek: DeepSeekClient):
        self.catalog = catalog
        self.deepseek = deepseek
        self.resolver = PortionResolver()

    @staticmethod
    def _method_near(text: str, start: int, end: int) -> str | None:
        nearby = text[max(0, start - 6): min(len(text), end + 6)]
        return next((m for m in COOKING_METHODS if m in nearby), None)

    # ── regex-based parsing ──────────────────────────────────────────────

    def parse_rules(
        self, text: str, additional_food_names: list[str] | None = None
    ) -> MealParseResult:
        """V1.2: unit-first parsing.  Only falls back to plain-text matching
        when NO explicit units (gram or natural) were found anywhere in the input."""
        items: list[ParsedMealItem] = []
        seen: set[str] = set()
        extra_food_names = sorted(set(additional_food_names or []), key=len, reverse=True)
        has_any_unit_match = False

        # ── pass 1: gram units "食物名 X克" / "X克 食物名" ──
        for alias, food in self.catalog.all_aliases():
            if food.id in seen:
                continue
            match = self._match_gram_unit(alias, text)
            if not match:
                continue
            has_any_unit_match = True
            grams, method = match
            items.append(
                ParsedMealItem(
                    name=food.name, grams=grams,
                    cooking_method=method, confidence=1.0,
                )
            )
            seen.add(food.id)

        # ── pass 2: custom foods (gram units) ──
        for name in extra_food_names:
            marker = f"custom:{name}"
            if marker in seen:
                continue
            match = self._match_gram_unit(name, text)
            if not match:
                continue
            has_any_unit_match = True
            grams, method = match
            items.append(
                ParsedMealItem(name=name, grams=grams, cooking_method=method, confidence=1.0)
            )
            seen.add(marker)

        # ── pass 3: natural units "X个食物" / "食物 X个" ──
        for alias, food in self.catalog.all_aliases():
            if food.id in seen:
                continue
            match = self._match_natural_unit(alias, text, food.name)
            if not match:
                continue
            has_any_unit_match = True
            grams, unit, amount, confidence, note = match
            items.append(
                ParsedMealItem(name=food.name, grams=grams, confidence=confidence)
            )
            seen.add(food.id)

        # ── pass 4: vague quantifiers ──
        for alias, food in self.catalog.all_aliases():
            if food.id in seen:
                continue
            match = self._match_vague_quantifier(alias, text, food.name)
            if not match:
                continue
            has_any_unit_match = True
            grams, quant, confidence = match
            items.append(
                ParsedMealItem(name=food.name, grams=grams, confidence=confidence)
            )
            seen.add(food.id)

        # ── pass 5: composite foods ──
        for key, cf in COMPOSITE_FOODS.items():
            if re.search(re.escape(key), text, re.IGNORECASE) and f"composite:{key}" not in seen:
                has_any_unit_match = True
                confidence = {"low": 0.5, "medium": 0.6, "high": 0.35}[cf.uncertainty]
                grams = cf.default_grams if cf.default_grams > 0 else None
                item = ParsedMealItem(name=key, grams=grams, confidence=confidence)
                if cf.prompt:
                    item.brand = f"⚠{cf.prompt}"
                items.append(item)
                seen.add(f"composite:{key}")

        # ── pass 6: plain-text fallback — only when NO units were found ──
        if not has_any_unit_match:
            for alias, food in self.catalog.all_aliases():
                if food.id in seen:
                    continue
                if re.search(re.escape(alias), text, re.IGNORECASE):
                    items.append(
                        ParsedMealItem(name=food.name, grams=None, confidence=0.5)
                    )
                    seen.add(food.id)
                    if len(items) >= 12:  # cap fallback items to avoid spam
                        break

        # ── build result ──
        missing: list[str] = []
        if not items:
            missing.append("可识别的食物名称")
        elif any(item.grams is None for item in items):
            missing.append("每种食物的克数")

        return MealParseResult(items=items, missing_fields=missing, parser="rules")

    # ── regex helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_number(raw: str) -> float | None:
        """Parse a Chinese numeral or digit string into a float.  Returns None for '几'."""
        if raw in _CN_NUMERAL_MAP:
            val = _CN_NUMERAL_MAP[raw]
            return float(val) if val is not None else None
        try:
            return float(raw)
        except ValueError:
            return None

    def _match_gram_unit(
        self, alias: str, text: str
    ) -> tuple[float, str | None] | None:
        """Match '食物名 X克' or 'X克 食物名'.  Returns (grams, method) or None.
        V1.2: only matches when an explicit gram unit is present (no plain-text fallback).
        """
        escaped = re.escape(alias)
        after = re.search(
            rf"{escaped}\s*(?:约|大约|差不多)?\s*{_NUMBER_PAT}\s*{GRAM_UNITS}",
            text, re.IGNORECASE,
        )
        before = re.search(
            rf"(?:约|大约|差不多)?\s*{_NUMBER_PAT}\s*{GRAM_UNITS}\s*(?:的)?\s*{escaped}",
            text, re.IGNORECASE,
        )
        match = after or before
        if not match:
            return None
        num_val = self._parse_number(match.group(1))
        if num_val is None:
            return None
        grams_val = num_val * GRAM_FACTORS[match.group(2).lower()]
        method = self._method_near(text, match.start(), match.end())
        return (grams_val, method)

    def _match_natural_unit(
        self, alias: str, text: str, food_name: str
    ) -> tuple[float, str, float, float, str] | None:
        """Match 'X个食物名' or '食物名 X个' using the PortionResolver."""
        escaped = re.escape(alias)
        after = re.search(
            rf"{escaped}\s*(?:约|大约|差不多)?\s*{_NUMBER_PAT}\s*{NATURAL_UNITS}",
            text, re.IGNORECASE,
        )
        before = re.search(
            rf"(?:约|大约|差不多)?\s*{_NUMBER_PAT}\s*{NATURAL_UNITS}\s*(?:的)?\s*{escaped}",
            text, re.IGNORECASE,
        )
        match = after or before
        if not match:
            return None
        num_val = self._parse_number(match.group(1))
        if num_val is None:
            # "几个XX" — treat as vague, default to 1
            num_val = 1.0
        unit = match.group(2)
        est = self.resolver.resolve(food_name, num_val, unit)
        if not est:
            return None
        match_pos = match.start()  # for _method_near
        return (est.grams, unit, num_val, est.confidence, est.note)

    def _match_vague_quantifier(
        self, alias: str, text: str, food_name: str
    ) -> tuple[float, str, float] | None:
        """Match '食物名' preceded by a vague quantifier like '几口' or '一半'."""
        for quant, fraction in sorted(VAGUE_QUANTIFIERS.items(), key=lambda x: -len(x[0])):
            escaped_q = re.escape(quant)
            escaped_f = re.escape(alias)
            pattern = rf"{escaped_q}\s*{escaped_f}"
            if re.search(pattern, text, re.IGNORECASE):
                est = self.resolver.resolve(food_name, fraction, quant)
                if est:
                    return (est.grams, quant, est.confidence)
        return None

    # ── DeepSeek-enhanced parsing ─────────────────────────────────────────

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
