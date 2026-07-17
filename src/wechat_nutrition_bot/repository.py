from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from .models import (
    CustomFoodInput,
    DailyBalance,
    FoodRecord,
    MealCalculation,
    NutrientGap,
    Nutrients,
    ProfileDraft,
    ProfileDraftData,
    SavedMeal,
    UserProfileInput,
)
from .time_utils import classify_meal_period

NUTRIENT_COLUMNS = {
    "energy_kcal": "energy_kcal",
    "protein_g": "protein_g",
    "fat_g": "fat_g",
    "carbohydrate_g": "carbohydrate_g",
    "fiber_g": "fiber_g",
}


class Repository:
    """SQLite persistence with pseudonymous user identifiers."""

    def __init__(self, database_path: Path | str, hmac_secret: str):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.hmac_secret = hmac_secret.encode("utf-8")
        self.init_schema()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_key TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    user_key TEXT PRIMARY KEY REFERENCES users(user_key) ON DELETE CASCADE,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profile_drafts (
                    user_key TEXT PRIMARY KEY REFERENCES users(user_key) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    consented_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS meals (
                    meal_id TEXT PRIMARY KEY,
                    user_key TEXT NOT NULL REFERENCES users(user_key) ON DELETE CASCADE,
                    eaten_at TEXT NOT NULL,
                    meal_period TEXT NOT NULL DEFAULT 'evening',
                    note TEXT NOT NULL DEFAULT '',
                    source_message_id TEXT UNIQUE,
                    energy_kcal REAL NOT NULL,
                    protein_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    carbohydrate_g REAL NOT NULL,
                    fiber_g REAL NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS meal_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meal_id TEXT NOT NULL REFERENCES meals(meal_id) ON DELETE CASCADE,
                    food_id TEXT NOT NULL,
                    food_name TEXT NOT NULL,
                    grams REAL NOT NULL,
                    nutrients_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    data_status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS async_results (
                    user_key TEXT PRIMARY KEY REFERENCES users(user_key) ON DELETE CASCADE,
                    request_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_text TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS message_receipts (
                    message_id TEXT PRIMARY KEY,
                    response_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS custom_foods (
                    food_id TEXT PRIMARY KEY,
                    user_key TEXT NOT NULL REFERENCES users(user_key) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_key, normalized_name)
                );

                CREATE TABLE IF NOT EXISTS unknown_food_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL REFERENCES users(user_key) ON DELETE CASCADE,
                    food_name TEXT NOT NULL,
                    source_message TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS weight_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL REFERENCES users(user_key) ON DELETE CASCADE,
                    measured_at TEXT NOT NULL,
                    weight_kg REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_key, measured_at)
                );

                CREATE TABLE IF NOT EXISTS diagnostic_test_accounts (
                    user_key TEXT PRIMARY KEY REFERENCES users(user_key) ON DELETE CASCADE,
                    alias TEXT NOT NULL UNIQUE,
                    enabled_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagnostic_messages (
                    diagnostic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL REFERENCES users(user_key) ON DELETE CASCADE,
                    direction TEXT NOT NULL CHECK(direction IN ('inbound', 'outbound')),
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_message_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_meals_user_date
                ON meals(user_key, eaten_at);
                CREATE INDEX IF NOT EXISTS idx_unknown_food_user
                ON unknown_food_requests(user_key, created_at);
                CREATE INDEX IF NOT EXISTS idx_weight_user_date
                ON weight_records(user_key, measured_at);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_user_date
                ON diagnostic_messages(user_key, created_at);
                """
            )
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(meals)").fetchall()
            }
            needs_period_backfill = "meal_period" not in columns
            if needs_period_backfill:
                connection.execute(
                    "ALTER TABLE meals ADD COLUMN meal_period TEXT NOT NULL DEFAULT 'evening'"
                )
            period_filter = (
                ""
                if needs_period_backfill
                else """WHERE meal_period IS NULL OR meal_period NOT IN
                    ('breakfast', 'lunch', 'afternoon', 'evening')"""
            )
            connection.execute(
                f"""
                UPDATE meals SET meal_period = CASE
                    WHEN CAST(substr(eaten_at, 12, 2) AS INTEGER) BETWEEN 6 AND 10
                        THEN 'breakfast'
                    WHEN CAST(substr(eaten_at, 12, 2) AS INTEGER) BETWEEN 11 AND 13
                        THEN 'lunch'
                    WHEN CAST(substr(eaten_at, 12, 2) AS INTEGER) BETWEEN 14 AND 18
                        THEN 'afternoon'
                    ELSE 'evening'
                END
                {period_filter}
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def user_key(self, raw_user_id: str) -> str:
        return hmac.new(self.hmac_secret, raw_user_id.encode("utf-8"), hashlib.sha256).hexdigest()

    def _ensure_user(self, connection: sqlite3.Connection, user_key: str) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO users(user_key, created_at) VALUES (?, ?)",
            (user_key, self._now()),
        )

    def save_meal(
        self,
        raw_user_id: str,
        calculation: MealCalculation,
        eaten_at: datetime | None = None,
        note: str = "",
        source_message_id: str | None = None,
        meal_period: str | None = None,
    ) -> SavedMeal:
        if not calculation.items:
            raise ValueError("Cannot save a meal without resolved items")
        timestamp = eaten_at or datetime.now().astimezone()
        period = meal_period or classify_meal_period(timestamp)
        key = self.user_key(raw_user_id)
        meal_id = uuid.uuid4().hex
        with self.connection() as connection:
            self._ensure_user(connection, key)
            if source_message_id:
                existing = connection.execute(
                    "SELECT meal_id FROM meals WHERE source_message_id = ?", (source_message_id,)
                ).fetchone()
                if existing:
                    return self.get_meal(existing["meal_id"])
            totals = calculation.totals
            connection.execute(
                """
                INSERT INTO meals(
                    meal_id, user_key, eaten_at, meal_period, note, source_message_id,
                    energy_kcal, protein_g, fat_g, carbohydrate_g, fiber_g, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meal_id,
                    key,
                    timestamp.isoformat(),
                    period,
                    note,
                    source_message_id,
                    totals.energy_kcal,
                    totals.protein_g,
                    totals.fat_g,
                    totals.carbohydrate_g,
                    totals.fiber_g,
                    self._now(),
                ),
            )
            connection.executemany(
                """
                INSERT INTO meal_items(
                    meal_id, food_id, food_name, grams, nutrients_json, source, data_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        meal_id,
                        item.food_id,
                        item.food_name,
                        item.grams,
                        item.nutrients.model_dump_json(),
                        item.source,
                        item.data_status,
                    )
                    for item in calculation.items
                ],
            )
        return SavedMeal(
            meal_id=meal_id,
            user_key=key,
            eaten_at=timestamp,
            meal_period=period,
            calculation=calculation,
        )

    def get_meal(self, meal_id: str) -> SavedMeal:
        with self.connection() as connection:
            meal = connection.execute(
                "SELECT * FROM meals WHERE meal_id = ?", (meal_id,)
            ).fetchone()
            if meal is None:
                raise KeyError(meal_id)
            item_rows = connection.execute(
                "SELECT * FROM meal_items WHERE meal_id = ? ORDER BY item_id", (meal_id,)
            ).fetchall()
        from .models import CalculatedMealItem  # local import avoids a large module import cycle

        items = [
            CalculatedMealItem(
                food_id=row["food_id"],
                food_name=row["food_name"],
                grams=row["grams"],
                nutrients=Nutrients.model_validate_json(row["nutrients_json"]),
                source=row["source"],
                data_status=row["data_status"],
                calculation=f"每100克数据 × {row['grams']:g}/100",
            )
            for row in item_rows
        ]
        totals = Nutrients(**{field: meal[column] for field, column in NUTRIENT_COLUMNS.items()})
        calculation = MealCalculation(items=items, totals=totals, status="complete")
        return SavedMeal(
            meal_id=meal["meal_id"],
            user_key=meal["user_key"],
            eaten_at=datetime.fromisoformat(meal["eaten_at"]),
            meal_period=meal["meal_period"],
            calculation=calculation,
        )

    def upsert_profile(self, raw_user_id: str, profile: UserProfileInput) -> str:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            self._ensure_user(connection, key)
            connection.execute(
                """
                INSERT INTO profiles(user_key, payload_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(user_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (key, profile.model_dump_json(), self._now()),
            )
        return key

    def get_profile(self, raw_user_id: str) -> UserProfileInput | None:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM profiles WHERE user_key = ?", (key,)
            ).fetchone()
        return UserProfileInput.model_validate_json(row["payload_json"]) if row else None

    def save_profile_draft(
        self,
        raw_user_id: str,
        data: ProfileDraftData,
        status: str,
        consented_at: datetime | None = None,
    ) -> ProfileDraft:
        key = self.user_key(raw_user_id)
        now = self._now()
        with self.connection() as connection:
            self._ensure_user(connection, key)
            existing = connection.execute(
                "SELECT consented_at FROM profile_drafts WHERE user_key = ?", (key,)
            ).fetchone()
            consent_value = (
                consented_at.isoformat()
                if consented_at
                else (existing["consented_at"] if existing else None)
            )
            connection.execute(
                """
                INSERT INTO profile_drafts(
                    user_key, status, payload_json, consented_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_key) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    consented_at = excluded.consented_at,
                    updated_at = excluded.updated_at
                """,
                (key, status, data.model_dump_json(), consent_value, now),
            )
        return ProfileDraft(
            status=status,
            data=data,
            consented_at=datetime.fromisoformat(consent_value) if consent_value else None,
            updated_at=datetime.fromisoformat(now),
        )

    def get_profile_draft(self, raw_user_id: str) -> ProfileDraft | None:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT status, payload_json, consented_at, updated_at
                FROM profile_drafts WHERE user_key = ?
                """,
                (key,),
            ).fetchone()
        if not row:
            return None
        return ProfileDraft(
            status=row["status"],
            data=ProfileDraftData.model_validate_json(row["payload_json"]),
            consented_at=(
                datetime.fromisoformat(row["consented_at"]) if row["consented_at"] else None
            ),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _normalize_food_name(value: str) -> str:
        return "".join(value.lower().strip().split())

    def upsert_custom_food(self, raw_user_id: str, food: CustomFoodInput) -> FoodRecord:
        key = self.user_key(raw_user_id)
        normalized = self._normalize_food_name(food.name)
        food_id = "custom-" + hashlib.sha256(f"{key}:{normalized}".encode()).hexdigest()[:20]
        record = FoodRecord(
            id=food_id,
            name=food.name,
            aliases=list(
                dict.fromkeys([*food.aliases, food.brand] if food.brand else food.aliases)
            ),
            category="个人包装食品",
            nutrients_per_100g=food.nutrients_per_100g,
            source="用户提供的包装营养标签",
            data_status="label",
            notes=food.notes or "数值应与包装每100克营养成分表一致",
        )
        now = self._now()
        with self.connection() as connection:
            self._ensure_user(connection, key)
            connection.execute(
                """
                INSERT INTO custom_foods(
                    food_id, user_key, name, normalized_name, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_key, normalized_name) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (food_id, key, food.name, normalized, record.model_dump_json(), now, now),
            )
        return record

    def list_custom_foods(self, raw_user_id: str) -> list[FoodRecord]:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM custom_foods WHERE user_key = ? ORDER BY name", (key,)
            ).fetchall()
        return [FoodRecord.model_validate_json(row["payload_json"]) for row in rows]

    def record_unknown_food(
        self, raw_user_id: str, food_name: str, source_message: str = ""
    ) -> None:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            self._ensure_user(connection, key)
            connection.execute(
                """
                INSERT INTO unknown_food_requests(
                    user_key, food_name, source_message, status, created_at
                ) VALUES (?, ?, ?, 'open', ?)
                """,
                (key, food_name[:100], source_message[:500], self._now()),
            )

    def record_weight(
        self, raw_user_id: str, weight_kg: float, measured_at: datetime
    ) -> None:
        if not 15 <= weight_kg <= 400:
            raise ValueError("weight_kg must be between 15 and 400")
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            self._ensure_user(connection, key)
            connection.execute(
                """
                INSERT INTO weight_records(user_key, measured_at, weight_kg, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_key, measured_at) DO UPDATE SET weight_kg = excluded.weight_kg
                """,
                (key, measured_at.isoformat(), weight_kg, self._now()),
            )

    def get_weight_records(self, raw_user_id: str, limit: int = 28) -> list[dict[str, object]]:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT measured_at, weight_kg FROM weight_records
                WHERE user_key = ? ORDER BY measured_at DESC LIMIT ?
                """,
                (key, max(1, min(limit, 365))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def bind_diagnostic_test_account(self, raw_user_id: str, alias: str) -> bool:
        """Bind one visible test alias to a pseudonymous user key without storing OpenID."""
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            self._ensure_user(connection, key)
            existing = connection.execute(
                "SELECT user_key FROM diagnostic_test_accounts WHERE alias = ?", (alias,)
            ).fetchone()
            if existing and existing["user_key"] != key:
                return False
            connection.execute(
                """
                INSERT INTO diagnostic_test_accounts(user_key, alias, enabled_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_key) DO UPDATE SET
                    alias = excluded.alias,
                    enabled_at = excluded.enabled_at
                """,
                (key, alias, self._now()),
            )
        return True

    def is_diagnostic_test_account(self, raw_user_id: str) -> bool:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM diagnostic_test_accounts WHERE user_key = ?", (key,)
            ).fetchone()
        return row is not None

    def save_diagnostic_message(
        self,
        raw_user_id: str,
        direction: str,
        content: str,
        message_type: str = "text",
        source_message_id: str | None = None,
        created_at: datetime | None = None,
    ) -> bool:
        if direction not in {"inbound", "outbound"}:
            raise ValueError("direction must be inbound or outbound")
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            bound = connection.execute(
                "SELECT 1 FROM diagnostic_test_accounts WHERE user_key = ?", (key,)
            ).fetchone()
            if not bound:
                return False
            connection.execute(
                """
                INSERT INTO diagnostic_messages(
                    user_key, direction, message_type, content, source_message_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    direction,
                    message_type[:30],
                    content[:4000],
                    source_message_id,
                    (created_at.isoformat() if created_at else self._now()),
                ),
            )
        return True

    def get_diagnostic_messages(self, alias: str, limit: int = 30) -> list[dict[str, object]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT m.direction, m.message_type, m.content,
                       m.source_message_id, m.created_at
                FROM diagnostic_messages AS m
                JOIN diagnostic_test_accounts AS a ON a.user_key = m.user_key
                WHERE a.alias = ?
                ORDER BY m.diagnostic_id DESC
                LIMIT ?
                """,
                (alias, max(1, min(limit, 200))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def is_diagnostic_alias_bound(self, alias: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM diagnostic_test_accounts WHERE alias = ?", (alias,)
            ).fetchone()
        return row is not None

    @staticmethod
    def _profile_targets(profile: UserProfileInput | None) -> Nutrients | None:
        if profile is None:
            return None
        values = {
            "energy_kcal": profile.daily_energy_kcal,
            "protein_g": profile.daily_protein_g,
            "fat_g": profile.daily_fat_g,
            "carbohydrate_g": profile.daily_carbohydrate_g,
            "fiber_g": profile.daily_fiber_g,
        }
        if any(value is None for value in values.values()):
            return None
        return Nutrients(**values)  # type: ignore[arg-type]

    def get_daily_balance(self, raw_user_id: str, day: date) -> DailyBalance:
        key = self.user_key(raw_user_id)
        prefix = day.isoformat()
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS meal_count,
                       COALESCE(SUM(energy_kcal), 0) AS energy_kcal,
                       COALESCE(SUM(protein_g), 0) AS protein_g,
                       COALESCE(SUM(fat_g), 0) AS fat_g,
                       COALESCE(SUM(carbohydrate_g), 0) AS carbohydrate_g,
                       COALESCE(SUM(fiber_g), 0) AS fiber_g
                FROM meals WHERE user_key = ? AND substr(eaten_at, 1, 10) = ?
                """,
                (key, prefix),
            ).fetchone()
            period_rows = connection.execute(
                """
                SELECT meal_period,
                       COALESCE(SUM(energy_kcal), 0) AS energy_kcal,
                       COALESCE(SUM(protein_g), 0) AS protein_g,
                       COALESCE(SUM(fat_g), 0) AS fat_g,
                       COALESCE(SUM(carbohydrate_g), 0) AS carbohydrate_g,
                       COALESCE(SUM(fiber_g), 0) AS fiber_g
                FROM meals
                WHERE user_key = ? AND substr(eaten_at, 1, 10) = ?
                GROUP BY meal_period
                """,
                (key, prefix),
            ).fetchall()
        intake = Nutrients(**{field: row[column] for field, column in NUTRIENT_COLUMNS.items()})
        targets = self._profile_targets(self.get_profile(raw_user_id))
        by_period = {
            period: Nutrients()
            for period in ("breakfast", "lunch", "afternoon", "evening")
        }
        for period_row in period_rows:
            by_period[period_row["meal_period"]] = Nutrients(
                **{
                    field: period_row[column]
                    for field, column in NUTRIENT_COLUMNS.items()
                }
            )
        remaining = None
        notes: list[str] = []
        if targets:
            remaining = Nutrients(
                **{
                    field: max(0, round(getattr(targets, field) - getattr(intake, field), 3))
                    for field in NUTRIENT_COLUMNS
                }
            )
        else:
            notes.append("尚未设置完整的每日营养目标，仅显示已记录摄入量")
        return DailyBalance(
            user_key=key,
            day=day,
            intake=intake,
            targets=targets,
            remaining=remaining,
            meal_count=row["meal_count"],
            by_meal_period=by_period,
            notes=notes,
        )

    def get_nutrient_gap(self, raw_user_id: str, start: date, end: date) -> NutrientGap:
        if end < start:
            raise ValueError("end_date must be on or after start_date")
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(DISTINCT substr(eaten_at, 1, 10)) AS days_with_records,
                       COALESCE(SUM(energy_kcal), 0) AS energy_kcal,
                       COALESCE(SUM(protein_g), 0) AS protein_g,
                       COALESCE(SUM(fat_g), 0) AS fat_g,
                       COALESCE(SUM(carbohydrate_g), 0) AS carbohydrate_g,
                       COALESCE(SUM(fiber_g), 0) AS fiber_g
                FROM meals
                WHERE user_key = ? AND substr(eaten_at, 1, 10) BETWEEN ? AND ?
                """,
                (key, start.isoformat(), end.isoformat()),
            ).fetchone()
        days = row["days_with_records"]
        average = Nutrients(
            **{
                field: round(row[column] / days, 3) if days else 0
                for field, column in NUTRIENT_COLUMNS.items()
            }
        )
        targets = self._profile_targets(self.get_profile(raw_user_id))
        gaps = None
        notes: list[str] = []
        if targets:
            gaps = Nutrients(
                **{
                    field: max(0, round(getattr(targets, field) - getattr(average, field), 3))
                    for field in NUTRIENT_COLUMNS
                }
            )
        else:
            notes.append("尚未设置完整目标，无法计算缺口")
        if days < (end - start).days + 1:
            notes.append("区间内并非每天都有饮食记录，平均值可能低估实际摄入")
        return NutrientGap(
            user_key=key,
            start_date=start,
            end_date=end,
            days_with_records=days,
            daily_average=average,
            targets=targets,
            gaps=gaps,
            notes=notes,
        )

    def set_async_result(
        self, raw_user_id: str, request_id: str, status: str, response_text: str | None = None
    ) -> None:
        key = self.user_key(raw_user_id)
        self.set_async_result_by_key(key, request_id, status, response_text)

    def set_async_result_by_key(
        self, user_key: str, request_id: str, status: str, response_text: str | None = None
    ) -> None:
        with self.connection() as connection:
            self._ensure_user(connection, user_key)
            connection.execute(
                """
                INSERT INTO async_results(user_key, request_id, status, response_text, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_key) DO UPDATE SET
                    request_id = excluded.request_id,
                    status = excluded.status,
                    response_text = excluded.response_text,
                    updated_at = excluded.updated_at
                """,
                (user_key, request_id, status, response_text, self._now()),
            )

    def get_async_result(self, raw_user_id: str) -> dict[str, str | None] | None:
        key = self.user_key(raw_user_id)
        return self.get_async_result_by_key(key)

    def get_async_result_by_key(self, user_key: str) -> dict[str, str | None] | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT request_id, status, response_text, updated_at
                FROM async_results WHERE user_key = ?
                """,
                (user_key,),
            ).fetchone()
        return dict(row) if row else None

    def get_active_user_keys_for_date(self, day_iso: str) -> list[str]:
        """Return all user_keys with meals on a given date. Used by daily summary scheduler."""
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT user_key FROM meals WHERE substr(eaten_at, 1, 10) = ?",
                (day_iso,),
            ).fetchall()
        return [r["user_key"] for r in rows]

    def get_message_receipt(self, message_id: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT response_text FROM message_receipts WHERE message_id = ?", (message_id,)
            ).fetchone()
        return row["response_text"] if row else None

    def save_message_receipt(self, message_id: str, response_text: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO message_receipts(message_id, response_text, created_at)
                VALUES (?, ?, ?)
                """,
                (message_id, response_text, self._now()),
            )

    def delete_user_data(self, raw_user_id: str) -> bool:
        key = self.user_key(raw_user_id)
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM users WHERE user_key = ?", (key,))
        return cursor.rowcount > 0

    def export_profile_summary(self, raw_user_id: str) -> dict[str, object]:
        profile = self.get_profile(raw_user_id)
        return json.loads(profile.model_dump_json()) if profile else {}
