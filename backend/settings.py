"""Human-only, non-secret application settings."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.db.database import initialize_database

SAFE_KEYS = {
    "gemini_model", "agent_max_steps", "default_terminal", "browser_enabled",
    "allowed_roots", "confirmation_behavior", "log_retention_days",
    "memory_enabled", "computer_use_enabled",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SettingsStore:
    def __init__(self, database_path: Path, defaults: Settings) -> None:
        self.database_path = database_path
        self.defaults = {key: getattr(defaults, key) for key in SAFE_KEYS}
        initialize_database(database_path)

    def get(self) -> dict[str, Any]:
        values = dict(self.defaults)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("SELECT key, value_json FROM settings").fetchall()
        for key, value in rows:
            if key in SAFE_KEYS:
                values[key] = json.loads(value)
        return values

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        unknown = set(changes) - SAFE_KEYS
        if unknown:
            raise ValueError(f"Unsupported or secret setting: {sorted(unknown)[0]}")
        values = self.get()
        values.update(changes)
        if values["agent_max_steps"] < 1 or values["agent_max_steps"] > 100:
            raise ValueError("agent_max_steps must be between 1 and 100")
        if values["log_retention_days"] < 1:
            raise ValueError("log_retention_days must be positive")
        if values["confirmation_behavior"] not in {"ask", "always"}:
            raise ValueError("confirmation_behavior must be ask or always")
        timestamp = _now()
        with sqlite3.connect(self.database_path) as connection:
            for key, value in changes.items():
                connection.execute("INSERT INTO settings(key, value_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at", (key, json.dumps(value), timestamp))
        return values
