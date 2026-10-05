"""Small per-task event bus with monotonic event IDs."""

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class TaskEvent:
    id: int
    task_id: str
    type: str
    timestamp: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    def __init__(self) -> None:
        self._events: dict[str, list[TaskEvent]] = {}
        self._queues: dict[str, list[asyncio.Queue[TaskEvent]]] = {}

    def emit(self, task_id: str, event_type: str, payload: dict[str, Any] | None = None) -> TaskEvent:
        events = self._events.setdefault(task_id, [])
        event = TaskEvent(len(events) + 1, task_id, event_type, datetime.now(UTC).isoformat(), payload or {})
        events.append(event)
        for queue in self._queues.get(task_id, []):
            queue.put_nowait(event)
        return event

    def history(self, task_id: str, after_id: int = 0) -> list[TaskEvent]:
        return [event for event in self._events.get(task_id, []) if event.id > after_id]

    async def subscribe(self, task_id: str, after_id: int = 0):
        queue: asyncio.Queue[TaskEvent] = asyncio.Queue()
        self._queues.setdefault(task_id, []).append(queue)
        try:
            for event in self.history(task_id, after_id):
                yield event
            while True:
                yield await queue.get()
        finally:
            self._queues[task_id].remove(queue)

