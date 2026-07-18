from __future__ import annotations

from wechat_nutrition_bot.models import MealItemInput


def test_lookup_food_finds_chinese_alias(components):
    result = components.service.lookup_food("米饭")
    assert result["matches"][0]["id"] == "rice-cooked-white"
    assert result["matches"][0]["nutrients_per_100g"]["energy_kcal"] == 116


def test_calculate_meal_is_deterministic(components):
    result = components.calculator.calculate(
        [
            MealItemInput(food_id="rice-cooked-white", grams=200),
            MealItemInput(food_id="chicken-breast-cooked", grams=150),
            MealItemInput(food_id="cooking-oil", grams=8),
        ]
    )
    assert result.status == "complete"
    assert result.totals.energy_kcal == 551.5
    assert result.totals.protein_g == 51.7
    assert result.totals.fat_g == 14.0
    assert result.totals.carbohydrate_g == 51.8


def test_unresolved_food_is_not_calculated(components):
    result = components.service.calculate_meal([{"name": "神秘营养餐", "grams": 100}])
    assert result["status"] == "needs_clarification"
    assert result["totals"]["energy_kcal"] == 0
    assert result["unresolved"] == ["神秘营养餐"]
