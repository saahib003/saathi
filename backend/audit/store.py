"""SQLite audit storage."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.audit.redaction import redact_value


class AuditStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def record(self, task_id: str, kind: str, data: dict, status: str, duration_ms: int | None = None, tool_call_id: str | None = None) -> str:
        entry_id = str(uuid4())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO audit_entries(id, task_id, kind, tool_call_id, status, data_json, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (entry_id, task_id, kind, tool_call_id, status, json.dumps(redact_value(data)), duration_ms, datetime.now(UTC).isoformat()),
            )
        return entry_id

    def list_for_task(self, task_id: str) -> list[dict]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("SELECT id, kind, tool_call_id, status, data_json, duration_ms, created_at FROM audit_entries WHERE task_id = ? ORDER BY created_at", (task_id,)).fetchall()
        return [{"id": row[0], "kind": row[1], "tool_call_id": row[2], "status": row[3], "data": json.loads(row[4]), "duration_ms": row[5], "created_at": row[6]} for row in rows]

