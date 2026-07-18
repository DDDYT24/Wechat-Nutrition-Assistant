from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from .models import FoodRecord


class FoodCatalog:
    """Read-only controlled food catalog used by every calculation surface.

    V1.2: supports large-scale catalogs (1600+ foods), category filtering,
    and pre-computed indexes for fast lookup.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.version: str = payload["catalog_version"]
        self.disclaimer: str = payload["disclaimer"]
        self.foods = [FoodRecord.model_validate(food) for food in payload["foods"]]
        self._by_id = {food.id: food for food in self.foods}
        self._names: list[tuple[str, FoodRecord]] = []
        self._by_category: dict[str, list[FoodRecord]] = {}
        for food in self.foods:
            cat = food.category
            self._by_category.setdefault(cat, []).append(food)
            # Collect all name variants: canonical + existing aliases + auto-generated
            name_variants = {food.name, *food.aliases, *self._generate_common_aliases(food.name)}
            for name in name_variants:
                if name.strip():
                    self._names.append((self._normalize(name), food))
        # Pre-sort names by length desc so longer (more specific) matches come first
        self._names.sort(key=lambda item: len(item[0]), reverse=True)

    @staticmethod
    def _generate_common_aliases(name: str) -> list[str]:
        """Auto-generate shorter search-friendly aliases from 6th-edition scientific names.

        Examples:
          '鸡胸脯肉' → ['鸡胸肉', '鸡胸']
          '鸡蛋(白皮)' → ['鸡蛋']
          '稻米(代表值)' → ['稻米', '大米']
          '猪肉(肥瘦)(均值)' → ['猪肉']
        """
        import re
        aliases: list[str] = []
        cleaned = re.sub(r"[（(][^）)]*[）)]", "", name).strip()
        if cleaned and cleaned != name:
            aliases.append(cleaned)
        # Remove common suffixes
        for suffix in ["(代表值)", "（代表值）", "(均值)", "（均值）", "(肥瘦)", "（肥瘦）"]:
            short = name.replace(suffix, "").strip()
            if short and short != name and short not in aliases:
                aliases.append(short)
        # Compound-word shortening: drop the last character when reasonable
        # e.g. "鸡胸脯肉" → "鸡胸肉", "猪五花肉" → "五花肉"
        if len(cleaned) >= 4 and not any(c in cleaned for c in "奶油菜汤酱汁粉糕酥饼"):
            if cleaned.endswith("脯肉"):
                aliases.append(cleaned[:-2] + "肉")
            elif cleaned.endswith("腿肉"):
                aliases.append(cleaned[:-2] + "肉")
        return [a for a in dict.fromkeys(aliases) if a]

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(value.lower().strip().split())

    def get(self, food_id: str) -> FoodRecord | None:
        return self._by_id.get(food_id)

    def exact(self, query: str) -> FoodRecord | None:
        normalized = self._normalize(query)
        for name, food in self._names:
            if name == normalized:
                return food
        return None

    def search(
        self, query: str, limit: int = 5, category: str | None = None
    ) -> list[dict[str, object]]:
        """Fuzzy search with optional category filter.  V1.2: efficient for 1600+ foods."""
        normalized = self._normalize(query)
        if not normalized:
            return []
        # narrow candidate pool when category is specified
        candidates = self._names
        if category:
            cat_foods = self._by_category.get(category, [])
            cat_ids = {f.id for f in cat_foods}
            candidates = [(n, f) for n, f in self._names if f.id in cat_ids]
            if not candidates:
                candidates = self._names  # fallback
        scores: dict[str, tuple[float, FoodRecord, str]] = {}
        for name, food in candidates:
            if name == normalized:
                score = 1.0
            elif name.startswith(normalized) or normalized in name:
                score = 0.9
            else:
                score = SequenceMatcher(None, normalized, name).ratio()
            current = scores.get(food.id)
            if current is None or score > current[0]:
                scores[food.id] = (score, food, name)
        ranked = sorted(scores.values(), key=lambda item: (-item[0], item[1].name))
        return [
            {"score": round(score, 3), "matched_name": matched, **food.model_dump()}
            for score, food, matched in ranked[: max(1, min(limit, 20))]
            if score >= 0.35
        ]

    @property
    def categories(self) -> list[str]:
        """Return sorted list of all food categories in this catalog."""
        return sorted(self._by_category.keys())

    def all_aliases(self) -> list[tuple[str, FoodRecord]]:
        return sorted(self._names, key=lambda item: len(item[0]), reverse=True)
