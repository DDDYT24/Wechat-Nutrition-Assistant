from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from .models import FoodRecord


class FoodCatalog:
    """Read-only controlled food catalog used by every calculation surface."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.version: str = payload["catalog_version"]
        self.disclaimer: str = payload["disclaimer"]
        self.foods = [FoodRecord.model_validate(food) for food in payload["foods"]]
        self._by_id = {food.id: food for food in self.foods}
        self._names: list[tuple[str, FoodRecord]] = []
        for food in self.foods:
            for name in {food.name, *food.aliases}:
                self._names.append((self._normalize(name), food))

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

    def search(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        normalized = self._normalize(query)
        if not normalized:
            return []
        scores: dict[str, tuple[float, FoodRecord, str]] = {}
        for name, food in self._names:
            if name == normalized:
                score = 1.0
            elif normalized in name or name in normalized:
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

    def all_aliases(self) -> list[tuple[str, FoodRecord]]:
        return sorted(self._names, key=lambda item: len(item[0]), reverse=True)
