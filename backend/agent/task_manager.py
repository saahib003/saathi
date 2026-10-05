"""SQLite-backed task, tool-call, and approval state."""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.agent.state import TaskState, validate_transition
from backend.audit.store import AuditStore
from backend.db.database import initialize_database
from backend.tools.base import ToolResult


def now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Task:
    id: str
    user_message: str
    state: TaskState = TaskState.PENDING
    final_response: str | None = None
    cancel_requested: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class TaskManager:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._tasks: dict[str, Task] = {}
        self._initialize_tables()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize_tables(self) -> None:
        initialize_database(self.database_path)

    def create(self, user_message: str) -> Task:
        task = Task(str(uuid4()), user_message)
        timestamp = now()
        with self._connect() as connection:
            connection.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)", (task.id, task.user_message, task.state.value, None, 0, timestamp, timestamp))
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Task:
        if task_id in self._tasks:
            return self._tasks[task_id]
        with self._connect() as connection:
            row = connection.execute("SELECT id, user_message, state, final_response, cancel_requested FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown task: {task_id}")
        task = Task(row[0], row[1], TaskState(row[2]), row[3], bool(row[4]))
        self._tasks[task.id] = task
        return task

    def list(self) -> list[Task]:
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM tasks ORDER BY created_at DESC").fetchall()
        return [self.get(row[0]) for row in rows]

    def transition(self, task_id: str, target: TaskState) -> Task:
        task = self.get(task_id)
        validate_transition(task.state, target)
        task.state = target
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET state = ?, updated_at = ? WHERE id = ?", (target.value, now(), task_id))
        return task

    def finish(self, task_id: str, state: TaskState, response: str | None = None) -> Task:
        task = self.transition(task_id, state)
        task.final_response = response
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET final_response = ?, updated_at = ? WHERE id = ?", (response, now(), task_id))
        return task

    def request_cancel(self, task_id: str) -> Task:
        task = self.get(task_id)
        task.cancel_requested = True
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET cancel_requested = 1, updated_at = ? WHERE id = ?", (now(), task_id))
        return task

    def add_tool_call(self, task_id: str, name: str, arguments: dict) -> str:
        call_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("INSERT INTO tool_calls VALUES (?, ?, ?, ?, ?, ?, ?)", (call_id, task_id, name, json.dumps(arguments), None, "REQUESTED", now()))
        return call_id

    def complete_tool_call(self, call_id: str, result: ToolResult) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE tool_calls SET result_json = ?, status = ? WHERE id = ?", (json.dumps(result.to_dict()), "COMPLETED" if result.success else "FAILED", call_id))

    def add_approval(self, task_id: str, tool_call_id: str, arguments_hash: str) -> str:
        approval_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("INSERT INTO approvals(id, task_id, tool_call_id, decision, created_at, resolved_at, arguments_hash, scope_type, scope_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (approval_id, task_id, tool_call_id, None, now(), None, arguments_hash, "one_time", None))
        return approval_id

    def resolve_approval(self, approval_id: str, decision: str, scope_type: str = "one_time", scope_value: str | None = None) -> tuple[str, str]:
        if decision not in {"approve", "reject"}:
            raise ValueError("Decision must be approve or reject")
        with self._connect() as connection:
            row = connection.execute("SELECT task_id, tool_call_id, decision FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown approval: {approval_id}")
            if row[2] is not None:
                raise ValueError("Approval has already been resolved")
            connection.execute("UPDATE approvals SET decision = ?, scope_type = ?, scope_value = ?, resolved_at = ? WHERE id = ?", (decision, scope_type, scope_value, now(), approval_id))
        return row[0], row[1]

    def get_approval(self, approval_id: str) -> tuple[str, str]:
        with self._connect() as connection:
            row = connection.execute("SELECT task_id, tool_call_id FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown approval: {approval_id}")
        return row[0], row[1]

    def details(self, task_id: str) -> dict:
        task = self.get(task_id)
        with self._connect() as connection:
            tools = connection.execute("SELECT id, name, arguments_json, result_json, status, created_at FROM tool_calls WHERE task_id = ? ORDER BY created_at", (task_id,)).fetchall()
            approvals = connection.execute("SELECT id, tool_call_id, decision, created_at, resolved_at, arguments_hash, scope_type, scope_value FROM approvals WHERE task_id = ? ORDER BY created_at", (task_id,)).fetchall()
        return {
            **task.to_dict(),
            "tool_calls": [{"id": row[0], "name": row[1], "arguments": json.loads(row[2]), "result": json.loads(row[3]) if row[3] else None, "status": row[4], "created_at": row[5]} for row in tools],
            "approvals": [{"id": row[0], "tool_call_id": row[1], "decision": row[2], "created_at": row[3], "resolved_at": row[4], "arguments_hash": row[5], "scope_type": row[6], "scope_value": row[7]} for row in approvals],
            "audit": AuditStore(self.database_path).list_for_task(task_id),
        }
