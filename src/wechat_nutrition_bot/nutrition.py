from __future__ import annotations

from .catalog import FoodCatalog
from .models import CalculatedMealItem, FoodRecord, MealCalculation, MealItemInput, Nutrients


class NutritionCalculator:
    """Resolve foods and perform deterministic gram-based nutrition calculations."""

    def __init__(self, catalog: FoodCatalog):
        self.catalog = catalog

    def calculate(
        self, items: list[MealItemInput], additional_foods: list[FoodRecord] | None = None
    ) -> MealCalculation:
        calculated: list[CalculatedMealItem] = []
        unresolved: list[str] = []
        warnings: list[str] = []
        totals = Nutrients()
        extra_by_id = {food.id: food for food in additional_foods or []}
        extra_by_name = {
            self.catalog._normalize(name): food
            for food in additional_foods or []
            for name in {food.name, *food.aliases}
        }

        for item in items:
            food = self.catalog.get(item.food_id) if item.food_id else None
            if food is None and item.food_id:
                food = extra_by_id.get(item.food_id)
            if food is None and item.name:
                food = self.catalog.exact(item.name)
            if food is None and item.name:
                food = extra_by_name.get(self.catalog._normalize(item.name))
            if food is None:
                unresolved.append(item.name or item.food_id or "unknown")
                continue

            nutrients = food.nutrients_per_100g.scaled(item.grams / 100)
            totals = totals.plus(nutrients)
            calculated.append(
                CalculatedMealItem(
                    food_id=food.id,
                    food_name=food.name,
                    grams=round(item.grams, 2),
                    nutrients=nutrients,
                    source=food.source,
                    data_status=food.data_status,
                    calculation=f"每100克数据 × {item.grams:g}/100",
                )
            )
            if food.data_status == "seed":
                warnings.append(f"{food.name}使用种子数据，正式使用前需核验来源")
            if item.cooking_method and item.cooking_method not in food.notes:
                warnings.append(
                    f"{food.name}未单独计入“{item.cooking_method}”可能产生的额外油、糖或酱料"
                )

        if not calculated:
            status = "needs_clarification"
        elif unresolved:
            status = "partial"
        else:
            status = "complete"

        return MealCalculation(
            items=calculated,
            totals=totals,
            unresolved=unresolved,
            warnings=list(dict.fromkeys(warnings)),
            status=status,
        )
