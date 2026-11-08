from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from wechat_nutrition_bot.mcp_server import mcp


async def test_mcp_exposes_all_version_two_tools():
    names = {tool.name for tool in await mcp.list_tools()}
    assert names == {
        "lookup_food",
        "parse_meal",
        "calculate_meal",
        "save_meal",
        "get_daily_balance",
        "record_exercise",
        "get_daily_exercise",
        "get_nutrient_gap",
        "generate_weekly_review",
        "upsert_profile",
        "get_onboarding_status",
        "begin_onboarding",
        "record_profile_input",
        "confirm_profile",
        "calculate_energy_targets",
        "register_custom_food",
        "list_custom_foods",
        "record_weight",
        "get_weight_trend",
        "delete_user_data",
    }


async def test_mcp_lookup_food_returns_structured_result():
    _, structured = await mcp.call_tool("lookup_food", {"query": "米饭"})
    assert len(structured["matches"]) > 0
    m = structured["matches"][0]
    assert "米饭" in m["name"] or m["id"].startswith("cn6-")


async def test_mcp_exercise_rejects_model_generated_energy_field():
    with pytest.raises(ToolError, match="Extra inputs are not permitted"):
        await mcp.call_tool(
            "record_exercise",
            {
                "user_id": "mcp-exercise-user",
                "exercise": {
                    "type": "力量训练",
                    "duration_minutes": 90,
                    "intensity": "高",
                    "estimated_energy_kcal": 9999,
                },
            },
        )
