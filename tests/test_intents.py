from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from wechat_nutrition_bot.deepseek import DeepSeekClient
from wechat_nutrition_bot.models import StructuredIntentResult


def test_structured_intent_schema_rejects_model_generated_nutrition_numbers():
    with pytest.raises(ValidationError):
        StructuredIntentResult.model_validate(
            {
                "intent_types": ["meal_record"],
                "meal_text": "一个鸡蛋",
                "meal_items": [
                    {
                        "raw_name": "鸡蛋",
                        "catalog_name": "鸡蛋（代表值）",
                        "amount": 1,
                        "unit": "个",
                        "calories": 72,
                    }
                ],
            }
        )


async def test_deepseek_intents_reject_uncontrolled_food_and_non_source_segment():
    payload = """{
      "intent_types": ["meal_record", "training"],
      "meal_text": "模型改写的饮食",
      "meal_items": [{
        "raw_name": "神奇鸡蛋",
        "catalog_name": "模型鸡蛋",
        "amount": 1,
        "unit": "个",
        "needs_clarification": false
      }],
      "exercise_text": "练胸90分钟",
      "exercise": {
        "type": "力量训练",
        "duration_minutes": 90,
        "intensity": "高",
        "body_parts": ["胸"],
        "exercises": [],
        "steps": null
      },
      "notes": []
    }"""

    class FakeCompletions:
        async def create(self, **_kwargs):
            message = SimpleNamespace(content=payload)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = DeepSeekClient(
        api_key="",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        timeout_seconds=1,
    )
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    result = await client.parse_intents(
        "神奇鸡蛋；练胸90分钟",
        ["鸡蛋（代表值）"],
    )

    assert result.meal_text is None
    assert result.meal_items[0].catalog_name is None
    assert result.meal_items[0].needs_clarification is True
    assert result.exercise_text == "练胸90分钟"
    assert len(result.notes) == 2
