"""SQLite memory store; nothing is written unless the user explicitly asks."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.db.database import initialize_database

SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|password|token|secret|credential)\s*[=:]")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryStore:
    def __init__(self, database_path: Path, enabled: bool = True) -> None:
        self.database_path = database_path
        self.enabled = enabled
        initialize_database(database_path)

    def list(self) -> list[dict]:
        if not self.enabled:
            return []
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("SELECT id, content, tags_json, created_at, updated_at FROM memories ORDER BY updated_at DESC").fetchall()
        return [{"id": row[0], "content": row[1], "tags": json.loads(row[2]), "created_at": row[3], "updated_at": row[4]} for row in rows]

    def create(self, content: str, tags: list[str] | None = None) -> dict:
        if not self.enabled:
            raise ValueError("Memory is disabled")
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty")
        if SECRET_PATTERN.search(content):
            raise ValueError("Memory cannot contain credential-like key/value material")
        timestamp = _now()
        item = {"id": str(uuid4()), "content": content, "tags": tags or [], "created_at": timestamp, "updated_at": timestamp}
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("INSERT INTO memories(id, content, tags_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (item["id"], content, json.dumps(item["tags"]), timestamp, timestamp))
        return item

    def delete(self, memory_id: str) -> None:
        if not self.enabled:
            raise ValueError("Memory is disabled")
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        if cursor.rowcount == 0:
            raise KeyError(memory_id)

    def relevant(self, query: str, limit: int = 5) -> list[dict]:
        memories = self.list()
        words = {word.lower() for word in re.findall(r"[\w]{3,}", query)}
        scored = []
        for item in memories:
            haystack = f"{item['content']} {' '.join(item['tags'])}".lower()
            score = sum(1 for word in words if word in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["updated_at"]))
        return [item for _, item in scored[:limit]]
