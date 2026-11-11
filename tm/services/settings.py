"""Settings stored in ``app_settings``."""

from __future__ import annotations

import sqlite3

from pydantic import ValidationError

from tm.errors import bad_request, validation_details
from tm.models import Settings, SettingsUpdate

DEFAULTS: dict[str, str] = {
    "dayStart": "08:00",
    "dayEnd": "22:00",
    "weekStartsOn": "1",
    "granularityMin": "30",
    "bufferMin": "0",
    "maxRangeDays": "366",
    "maxChatMessages": "40",
}

DB_KEYS: dict[str, str] = {
    "day_start": "dayStart",
    "day_end": "dayEnd",
    "week_starts_on": "weekStartsOn",
    "granularity_min": "granularityMin",
    "buffer_min": "bufferMin",
    "max_range_days": "maxRangeDays",
    "max_chat_messages": "maxChatMessages",
}


def seed_defaults(conn: sqlite3.Connection) -> None:
    for key, value in DEFAULTS.items():
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()


def get_settings(conn: sqlite3.Connection) -> Settings:
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    raw = {row["key"]: row["value"] for row in rows}
    data: dict[str, object] = {}
    for field, key in DB_KEYS.items():
        if key in raw:
            data[field] = raw[key]
    return Settings(**data)


def update_settings(conn: sqlite3.Connection, patch: SettingsUpdate) -> Settings:
    current = get_settings(conn).model_dump()
    changes = patch.model_dump(exclude_unset=True)
    merged = {**current, **changes}
    try:
        updated = Settings(**merged)
    except ValidationError as exc:
        raise bad_request("invalid settings", validation_details(exc)) from exc

    with conn:
        for field, key in DB_KEYS.items():
            conn.execute(
                """
                INSERT INTO app_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(getattr(updated, field))),
            )
    return updated
