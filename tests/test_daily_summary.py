from wechat_nutrition_bot.daily_summary import (
    SUMMARY_SCHEDULE_HOUR,
    SUMMARY_SCHEDULE_MINUTE,
    DailySummaryScheduler,
)


def test_daily_summary_runs_at_2230():
    assert (SUMMARY_SCHEDULE_HOUR, SUMMARY_SCHEDULE_MINUTE) == (22, 30)


async def test_scheduler_generates_summary_for_hashed_active_user(components):
    user_id = "daily-summary-user"
    components.service.save_meal(
        user_id,
        [{"name": "米饭", "grams": 100}],
        source_message_id="daily-summary-meal",
    )

    await DailySummaryScheduler(components.service)._generate_all()

    stored = components.repository.get_async_result(user_id)
    assert stored is not None
    assert stored["status"] == "complete"
    assert "营养日报" in stored["response_text"]
