from __future__ import annotations

from datetime import date, datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from .container import build_components

components = build_components()
service = components.service
mcp = FastMCP(
    "WeChat Nutrition Tools V2",
    instructions=(
        "Use controlled food data and deterministic calculations. "
        "Never invent nutrition values for unresolved foods. "
        "Collect and confirm an adult profile before deriving targets. "
        "V1.1 is for general healthy-adult food logging, not medical treatment."
    ),
    json_response=True,
)


@mcp.tool()
def lookup_food(query: str, limit: int = 5) -> dict[str, Any]:
    """Search the controlled V1.1 food catalog and return sourced per-100g data."""
    return service.lookup_food(query, limit)


@mcp.tool()
async def parse_meal(text: str, user_id: str | None = None) -> dict[str, Any]:
    """Extract explicit foods, gram amounts and cooking methods without calculating nutrition."""
    return await service.parse_meal(text, user_id)


@mcp.tool()
def calculate_meal(
    items: list[dict[str, Any]], user_id: str | None = None
) -> dict[str, Any]:
    """Calculate nutrients from controlled food IDs or names and gram amounts."""
    return service.calculate_meal(items, user_id)


@mcp.tool()
def save_meal(
    user_id: str,
    items: list[dict[str, Any]],
    eaten_at: str | None = None,
    note: str = "",
    source_message_id: str | None = None,
) -> dict[str, Any]:
    """Calculate and persist a meal only when every food resolves to the controlled catalog."""
    timestamp = datetime.fromisoformat(eaten_at) if eaten_at else None
    return service.save_meal(user_id, items, timestamp, note, source_message_id)


@mcp.tool()
def get_daily_balance(user_id: str, day: str | None = None) -> dict[str, Any]:
    """Return saved daily intake and remaining values against complete user-set targets."""
    parsed_day = date.fromisoformat(day) if day else None
    return service.get_daily_balance(user_id, parsed_day)


@mcp.tool()
def get_nutrient_gap(user_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Compute average recorded intake and gaps over an inclusive date range."""
    return service.get_nutrient_gap(
        user_id, date.fromisoformat(start_date), date.fromisoformat(end_date)
    )


@mcp.tool()
def generate_weekly_review(user_id: str, week_start: str | None = None) -> dict[str, Any]:
    """Generate a deterministic weekly nutrition-log review from saved records."""
    parsed_start = date.fromisoformat(week_start) if week_start else None
    return service.generate_weekly_review(user_id, parsed_start)


@mcp.tool()
def upsert_profile(user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Save adult context and explicit targets without deriving treatment advice."""
    return service.upsert_profile(user_id, profile)


@mcp.tool()
def get_onboarding_status(user_id: str) -> dict[str, Any]:
    """Return consent, draft, confirmation and missing-field status for a user."""
    return service.get_onboarding_status(user_id)


@mcp.tool()
def begin_onboarding(user_id: str) -> dict[str, Any]:
    """Record profile-data consent and begin a resumable onboarding draft."""
    return service.begin_onboarding(user_id)


@mcp.tool()
def record_profile_input(user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge explicitly supplied profile fields into the unconfirmed draft."""
    return service.record_profile_input(user_id, updates)


@mcp.tool()
def confirm_profile(user_id: str) -> dict[str, Any]:
    """Confirm a complete adult profile and deterministically derive initial targets."""
    return service.confirm_profile(user_id)


@mcp.tool()
def calculate_energy_targets(profile: dict[str, Any]) -> dict[str, Any]:
    """Preview Mifflin-St Jeor plus PAL energy and macro targets without saving them."""
    return service.calculate_energy_targets(profile)


@mcp.tool()
def register_custom_food(user_id: str, food: dict[str, Any]) -> dict[str, Any]:
    """Register user-scoped per-100g package-label nutrition; never infer missing macros."""
    return service.register_custom_food(user_id, food)


@mcp.tool()
def list_custom_foods(user_id: str) -> dict[str, Any]:
    """List the user's package-label foods available to parsing and calculation."""
    return service.list_custom_foods(user_id)


@mcp.tool()
def record_weight(
    user_id: str, weight_kg: float, measured_at: str | None = None
) -> dict[str, Any]:
    """Save a dated weight for later trend-based target calibration."""
    timestamp = datetime.fromisoformat(measured_at) if measured_at else None
    return service.record_weight(user_id, weight_kg, timestamp)


@mcp.tool()
def get_weight_trend(user_id: str, limit: int = 28) -> dict[str, Any]:
    """Return recent weight observations and whether enough data exists for calibration."""
    return service.get_weight_trend(user_id, limit)


@mcp.tool()
def delete_user_data(user_id: str) -> dict[str, Any]:
    """Permanently delete the pseudonymous user's profile and all saved meal data."""
    return service.delete_user_data(user_id)


def run() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
