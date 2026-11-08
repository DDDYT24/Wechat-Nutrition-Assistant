"""V1.2 Daily summary generation and scheduled delivery.

Generates an end-of-day nutrition recap for users with recorded meals.
The scheduler runs at 22:30 Asia/Shanghai.  Summaries are stored as
async_results so the bridge can poll and deliver them to WeChat.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from .service import NutritionService
from .time_utils import as_shanghai, local_day

logger = logging.getLogger(__name__)

SUMMARY_SCHEDULE_HOUR = 22
SUMMARY_SCHEDULE_MINUTE = 30


def generate_daily_summary(
    service: NutritionService,
    user_id: str,
    day: date | None = None,
    *,
    user_id_is_key: bool = False,
) -> str | None:
    """Produce a compact daily nutrition summary for one user.

    Returns None when the user has no meals today (nothing to summarize).
    """
    target_day = day or local_day()
    balance = (
        service.repository.get_daily_balance_by_key(user_id, target_day).model_dump(mode="json")
        if user_id_is_key
        else service.get_daily_balance(user_id, target_day)
    )

    if balance["meal_count"] == 0:
        return None

    intake = balance["intake"]
    targets = balance["targets"]
    remaining = balance["remaining"]

    lines = [f"  {target_day.isoformat()} 营养日报"]
    lines.append("━" * 18)

    # Meal breakdown
    for period, label in [
        ("breakfast", "早餐"), ("lunch", "午餐"),
        ("afternoon", "下午"), ("evening", "晚餐"),
    ]:
        p = balance["by_meal_period"][period]
        if p["energy_kcal"] > 0:
            lines.append(f"  {label}  {p['energy_kcal']:.0f} kcal  "
                         f"P{p['protein_g']:.0f}g F{p['fat_g']:.0f}g C{p['carbohydrate_g']:.0f}g")

    lines.append("")
    lines.append(f"  今日摄入  {intake['energy_kcal']:.0f} kcal  "
                 f"蛋白质 {intake['protein_g']:.0f}g  "
                 f"脂肪 {intake['fat_g']:.0f}g  "
                 f"碳水 {intake['carbohydrate_g']:.0f}g")

    if targets:
        # Progress bars (ASCII)
        energy_pct = (min(100, int(intake["energy_kcal"] / targets["energy_kcal"] * 100))
                      if targets["energy_kcal"] else 0)
        protein_pct = (min(100, int(intake["protein_g"] / targets["protein_g"] * 100))
                       if targets["protein_g"] else 0)
        bar_e = _bar(energy_pct)
        bar_p = _bar(protein_pct)
        lines.append(f"  热量进度  {bar_e} {energy_pct}%  "
                     f"({intake['energy_kcal']:.0f}/{targets['energy_kcal']:.0f} kcal)")
        lines.append(f"  蛋白质    {bar_p} {protein_pct}%  "
                     f"({intake['protein_g']:.0f}/{targets['protein_g']:.0f} g)")
        if remaining:
            lines.append(f"  剩余配额  {remaining['energy_kcal']:.0f} kcal  "
                         f"P{remaining['protein_g']:.0f}g "
                         f"F{remaining['fat_g']:.0f}g "
                         f"C{remaining['carbohydrate_g']:.0f}g")

    # Weekly context
    today = target_day
    week_start = today - timedelta(days=today.weekday())
    gap_data = service.get_nutrient_gap(user_id, week_start, today)
    if gap_data["days_with_records"] >= 2:
        avg = gap_data["daily_average"]
        lines.append(f"\n  本周日均  {avg['energy_kcal']:.0f} kcal  "
                     f"({gap_data['days_with_records']}天记录)")

    lines.append("\n  明天继续加油！发送「帮助」查看功能。")
    return "\n".join(lines)


def _bar(pct: int, width: int = 8) -> str:
    """ASCII progress bar: '████░░░░'"""
    filled = min(width, max(0, int(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


# ── scheduler ────────────────────────────────────────────────────────────────


class DailySummaryScheduler:
    """Lightweight async scheduler — no external dependency needed."""

    def __init__(self, service: NutritionService):
        self.service = service
        self._task: asyncio.Task | None = None

    async def _run_loop(self) -> None:
        """Loop forever, checking every 60s whether it's time to generate summaries."""
        while True:
            now = as_shanghai()
            if (
                now.hour == SUMMARY_SCHEDULE_HOUR
                and now.minute == SUMMARY_SCHEDULE_MINUTE
            ):
                await self._generate_all()
                # Sleep 70s to avoid re-triggering within the same minute
                await asyncio.sleep(70)
            await asyncio.sleep(60)

    async def _generate_all(self) -> None:
        """Generate and store daily summaries for all active users."""
        today = local_day()
        logger.info("Generating daily summaries for %s", today.isoformat())

        user_keys = self.service.repository.get_active_user_keys_for_date(today.isoformat())
        count = 0
        for user_key in user_keys:
            summary = generate_daily_summary(
                self.service, user_key, today, user_id_is_key=True
            )
            if summary:
                try:
                    self.service.repository.set_async_result_by_key(
                        user_key, f"summary-{today.isoformat()}", "complete", summary
                    )
                    count += 1
                except Exception:
                    logger.exception("Failed to store summary for %s", user_key)

        logger.info("Generated %d daily summaries for %s", count, today.isoformat())

    def start(self) -> None:
        """Start the scheduler in the background."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Daily summary scheduler started (trigger at %02d:%02d Shanghai)",
            SUMMARY_SCHEDULE_HOUR,
            SUMMARY_SCHEDULE_MINUTE,
        )

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Daily summary scheduler stopped")


class PendingSummary:
    """Lightweight query for the bridge to poll."""

    def __init__(self, service: NutritionService):
        self.service = service

    def get_pending(self, user_id: str) -> str | None:
        """Return today's pending summary if available, or None."""
        today = local_day()
        stored = self.service.repository.get_async_result(user_id)
        if not stored:
            return None
        req_id = stored.get("request_id", "")
        if req_id == f"summary-{today.isoformat()}" and stored.get("status") == "complete":
            return stored.get("response_text")
        return None
