from __future__ import annotations

from wechat_nutrition_bot.models import ParsedMealItem


def test_rule_parser_extracts_explicit_grams(components):
    result = components.parser.parse_rules("午饭吃了米饭200克，鸡胸肉150g，炒菜油8克")
    items = {item.name: item.grams for item in result.items}
    assert items["熟白米饭"] == 200
    assert items["熟鸡胸肉"] == 150
    assert items["烹调油"] == 8
    assert result.missing_fields == []


def test_rule_parser_requires_weight(components):
    result = components.parser.parse_rules("今天吃了米饭和鸡胸肉")
    assert len(result.items) == 2
    assert result.missing_fields == ["每种食物的克数"]
    assert all(item.grams is None for item in result.items)


def test_rule_parser_supports_weight_before_food(components):
    result = components.parser.parse_rules("200克米饭，0.15kg鸡胸肉")
    items = {item.name: item.grams for item in result.items}
    assert items["熟白米饭"] == 200
    assert items["熟鸡胸肉"] == 150


def test_model_confidence_words_are_normalized():
    assert ParsedMealItem(name="米饭", grams=100, confidence="high").confidence == 0.9
    assert ParsedMealItem(name="米饭", grams=100, confidence="medium").confidence == 0.6
    assert ParsedMealItem(name="米饭", grams=100, confidence="unexpected").confidence == 0.5


async def test_parser_falls_back_when_deepseek_fails(components):
    class FailingDeepSeek:
        enabled = True

        async def parse_meal(self, text, allowed_food_names):
            raise RuntimeError("simulated provider outage")

    components.parser.deepseek = FailingDeepSeek()
    result = await components.parser.parse("吃了米饭")
    assert result.items[0].name == "熟白米饭"
    assert result.missing_fields == ["每种食物的克数"]
    assert "已降级" in result.notes[0]
