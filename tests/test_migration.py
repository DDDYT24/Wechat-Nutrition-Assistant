from __future__ import annotations

import sqlite3

from wechat_nutrition_bot.repository import Repository


def test_version_one_database_migrates_meal_period_without_data_loss(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (user_key TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE meals (
            meal_id TEXT PRIMARY KEY,
            user_key TEXT NOT NULL REFERENCES users(user_key) ON DELETE CASCADE,
            eaten_at TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            source_message_id TEXT UNIQUE,
            energy_kcal REAL NOT NULL,
            protein_g REAL NOT NULL,
            fat_g REAL NOT NULL,
            carbohydrate_g REAL NOT NULL,
            fiber_g REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO users VALUES ('legacy-user', '2026-07-16T00:00:00+00:00');
        INSERT INTO meals VALUES (
            'legacy-meal', 'legacy-user', '2026-07-16T12:30:00+08:00', '', 'legacy-msg',
            116, 2.6, 0.3, 25.9, 0.3, '2026-07-16T04:30:00+00:00'
        );
        """
    )
    connection.commit()
    connection.close()

    repository = Repository(path, "migration-test-secret")
    with repository.connection() as migrated:
        columns = {row["name"] for row in migrated.execute("PRAGMA table_info(meals)")}
        row = migrated.execute(
            "SELECT meal_period, energy_kcal FROM meals WHERE meal_id = 'legacy-meal'"
        ).fetchone()

    assert "meal_period" in columns
    assert row["meal_period"] == "lunch"
    assert row["energy_kcal"] == 116
