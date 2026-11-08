from __future__ import annotations

from wechat_nutrition_bot.agent import NutritionAgent
from wechat_nutrition_bot.container import build_components
from wechat_nutrition_bot.models import (
    EstimatedFoodItem,
    EstimatedMealResult,
    IntentExercise,
    IntentMealItem,
    Nutrients,
    StructuredIntentResult,
)

PROFILE_TEXT = (
    "男，28岁，175cm，72kg，久坐，增肌，训练2年，每周4天，"
    "不适用孕哺，无疾病、无用药、无过敏"
)


async def complete_onboarding(agent: NutritionAgent, user_id: str = "user-a") -> str:
    consent = await agent.handle_text(user_id, "同意并开始")
    assert "请按任意顺序" in consent
    review = await agent.handle_text(user_id, PROFILE_TEXT)
    assert "请核对资料" in review
    return await agent.handle_text(user_id, "确认资料")


async def test_agent_requires_consent_before_collecting(components):
    agent = NutritionAgent(components.service, components.deepseek)
    reply = await agent.handle_text("user-a", "米饭200克")
    assert "同意并开始" in reply
    assert components.service.get_daily_balance("user-a")["meal_count"] == 0


async def test_agent_collects_confirms_and_calculates_profile(components):
    agent = NutritionAgent(components.service, components.deepseek)
    reply = await complete_onboarding(agent)
    assert "资料已确认" in reply
    assert "2538 kcal" in reply
    profile = components.repository.get_profile("user-a")
    assert profile is not None
    assert profile.resting_energy_kcal == 1679
    assert profile.maintenance_energy_kcal == 2350
    assert profile.daily_energy_kcal == 2538


async def test_agent_calculates_and_saves_explicit_meal(components):
    agent = NutritionAgent(components.service, components.deepseek)
    await complete_onboarding(agent)
    reply = await agent.handle_text(
        "user-a", "米饭200克，鸡胸肉150克，烹调油8克", "agent-message-1"
    )
    assert "本餐：552 kcal" in reply
    assert "今日累计" in reply
    assert components.service.get_daily_balance("user-a")["meal_count"] == 1


async def test_agent_asks_for_missing_grams(components):
    agent = NutritionAgent(components.service, components.deepseek)
    await complete_onboarding(agent)
    reply = await agent.handle_text("user-a", "吃了米饭和鸡胸肉")
    assert "还需要这些食物的份量" in reply
    assert "不会输出伪精确热量" in reply


async def test_agent_requests_details_when_estimation_model_is_unavailable(components):
    agent = NutritionAgent(components.service, components.deepseek)
    await complete_onboarding(agent)
    reply = await agent.handle_text("user-a", "巧克力10克")
    assert "请写明食物和份量" in reply
    assert components.service.get_daily_balance("user-a")["meal_count"] == 0


async def test_agent_registers_and_logs_custom_food(components):
    agent = NutritionAgent(components.service, components.deepseek)
    await complete_onboarding(agent)
    registered = await agent.handle_text(
        "user-a",
        "登记食物 我的巧克力 每100克 热量550kcal 蛋白质7 脂肪35 碳水55 纤维5",
    )
    assert "已登记“我的巧克力”" in registered
    logged = await agent.handle_text("user-a", "我的巧克力10克", "custom-food-message")
    assert "本餐：55 kcal" in logged


async def test_agent_does_not_wait_for_deepseek_explanation(components):
    class FailingDeepSeek:
        enabled = True

    user_id = "fallback-user"
    components.service.begin_onboarding(user_id)
    components.service.record_profile_input(
        user_id,
        {
            "age": 28,
            "sex": "male",
            "height_cm": 175,
            "weight_kg": 72,
            "activity_level": "sedentary",
            "goal": "maintain",
            "training_years": 0,
            "training_days_per_week": 0,
            "pregnant_or_breastfeeding": False,
        },
    )
    components.service.confirm_profile(user_id)
    agent = NutritionAgent(components.service, FailingDeepSeek())
    reply = await agent.handle_text(user_id, "米饭200克", "fallback-message")
    assert "本餐：232 kcal" in reply
    assert components.service.get_daily_balance(user_id)["meal_count"] == 1


async def test_mixed_meal_and_training_records_each_mention_once(settings):
    project_root = settings.food_catalog_path.parents[1]
    v2_settings = settings.model_copy(
        update={"food_catalog_path": project_root / "data" / "foods_v2.json"}
    )
    components = build_components(v2_settings)
    agent = NutritionAgent(components.service, components.deepseek, components.profile_parser)
    user_id = "mixed-intent-user"
    await complete_onboarding(agent, user_id)
    text = "一个鸡蛋，一碗米饭，半碗粥；练胸和三头，90分钟，高强度"

    first = await agent.handle_text(user_id, text, "mixed-intent-message")
    duplicate = await agent.handle_text(user_id, text, "mixed-intent-message")

    with components.repository.connection() as connection:
        meal_items = connection.execute(
            "SELECT food_name, grams FROM meal_items ORDER BY item_id"
        ).fetchall()
    assert [(row["food_name"], row["grams"]) for row in meal_items] == [
        ("米饭（蒸，代表值）", 150.0),
        ("鸡蛋（代表值）", 50.0),
    ]
    assert "本餐：244 kcal" in first
    assert "训练已记录" in first
    assert "90分钟" in first
    assert duplicate == first
    assert components.service.get_daily_balance(user_id)["meal_count"] == 1
    exercises = components.service.get_daily_exercise(user_id)
    assert len(exercises) == 1
    assert exercises[0]["type"] == "力量训练"
    assert exercises[0]["duration_minutes"] == 90


async def test_agent_uses_structured_intent_segments_without_model_nutrition(settings):
    project_root = settings.food_catalog_path.parents[1]
    v2_settings = settings.model_copy(
        update={"food_catalog_path": project_root / "data" / "foods_v2.json"}
    )
    components = build_components(v2_settings)

    class StructuredDeepSeek:
        enabled = True

        async def parse_intents(self, _text, _allowed_food_names):
            return StructuredIntentResult(
                intent_types=["meal_record", "training"],
                meal_text="一个鸡蛋，一碗米饭，半碗粥",
                meal_items=[
                    IntentMealItem(
                        raw_name="鸡蛋",
                        catalog_name="鸡蛋（代表值）",
                        amount=1,
                        unit="个",
                    ),
                    IntentMealItem(
                        raw_name="米饭",
                        catalog_name="米饭（蒸，代表值）",
                        amount=1,
                        unit="碗",
                    ),
                    IntentMealItem(
                        raw_name="粥",
                        amount=0.5,
                        unit="碗",
                        needs_clarification=True,
                    ),
                ],
                exercise_text="练胸和三头，90分钟，高强度",
                exercise=IntentExercise(
                    type="力量训练",
                    duration_minutes=90,
                    intensity="高",
                    body_parts=["胸", "三头"],
                ),
            )

        async def estimate_foods(self, _text, names):
            assert names == ["粥"]
            return EstimatedMealResult(
                items=[
                    EstimatedFoodItem(
                        name="粥",
                        grams=150,
                        nutrients_per_100g=Nutrients(
                            energy_kcal=46,
                            protein_g=1.1,
                            fat_g=0.3,
                            carbohydrate_g=9.8,
                            fiber_g=0.4,
                        ),
                        confidence=0.65,
                        assumptions="按半碗普通白粥估算",
                    )
                ]
            )

    agent = NutritionAgent(
        components.service,
        StructuredDeepSeek(),
        components.profile_parser,
    )
    user_id = "structured-intent-user"
    await complete_onboarding(agent, user_id)
    reply = await agent.handle_text(
        user_id,
        "一个鸡蛋，一碗米饭，半碗粥；练胸和三头，90分钟，高强度",
        "structured-intent-message",
    )

    assert "本餐：312 kcal" in reply
    assert "训练已记录" in reply
    assert "粥 ≈150g（大模型估算）" in reply
    assert components.service.get_daily_balance(user_id)["meal_count"] == 1
    assert len(components.service.get_daily_exercise(user_id)) == 1


async def test_agent_uses_llm_for_remaining_calorie_and_food_advice(components):
    base_agent = NutritionAgent(components.service, components.deepseek)
    user_id = "nutrition-query-user"
    await complete_onboarding(base_agent, user_id)

    class AdviceDeepSeek:
        enabled = True

        async def answer_nutrition_question(self, text, daily_balance, profile):
            assert "还可以吃多少" in text
            assert daily_balance["remaining"] is not None
            assert profile["goal"] == "gain"
            return "今天还可以吃约2538 kcal。下一餐可选择鸡胸肉、米饭和蔬菜。"

    agent = NutritionAgent(components.service, AdviceDeepSeek(), components.profile_parser)
    reply = await agent.handle_text(user_id, "帮我算一下今日热量还可以吃多少，接下来吃什么")

    assert reply == "今天还可以吃约2538 kcal。下一餐可选择鸡胸肉、米饭和蔬菜。"
