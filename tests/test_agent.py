from __future__ import annotations

from wechat_nutrition_bot.agent import NutritionAgent

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


async def test_agent_handles_ambiguous_chocolate_without_inventing(components):
    agent = NutritionAgent(components.service, components.deepseek)
    await complete_onboarding(agent)
    reply = await agent.handle_text("user-a", "巧克力10克")
    assert "牛奶巧克力10克" in reply
    assert "包装每100克" in reply
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
