"""SQLite-backed permission scopes."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class PermissionScope:
    ONE_TIME = "one_time"
    SCOPED = "scoped"
    PERMANENT = "permanent"


class PermissionStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def grant(self, tool_name: str, scope_type: str, scope_value: str | None = None) -> None:
        if scope_type not in {PermissionScope.SCOPED, PermissionScope.PERMANENT}:
            return
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO permissions(id, tool_name, scope_type, scope_value, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), tool_name, scope_type, scope_value, datetime.now(UTC).isoformat()),
            )

    def allows(self, tool_name: str, arguments: object) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("SELECT scope_type, scope_value FROM permissions WHERE tool_name = ?", (tool_name,)).fetchall()
        values = self._strings(arguments)
        for scope_type, scope_value in rows:
            if scope_type == PermissionScope.PERMANENT:
                return True
            if scope_type == PermissionScope.SCOPED and scope_value and any(value == scope_value or value.startswith(scope_value.rstrip("\\/") + "\\") or value.startswith(scope_value.rstrip("\\/") + "/") for value in values):
                return True
        return False

    @staticmethod
    def _strings(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [item for child in value.values() for item in PermissionStore._strings(child)]
        if isinstance(value, (list, tuple)):
            return [item for child in value for item in PermissionStore._strings(child)]
        return []

