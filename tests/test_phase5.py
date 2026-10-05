import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.events.bus import EventBus
from backend.llm.fake_client import FakeLLMClient
from backend.llm.schemas import LLMResponse
from main import create_app


def test_event_bus_replays_after_cursor() -> None:
    bus = EventBus()
    bus.emit("task-1", "task_started")
    bus.emit("task-1", "agent_thinking", {"step": 0})
    bus.emit("task-1", "task_completed")
    assert [event.id for event in bus.history("task-1", after_id=1)] == [2, 3]


def test_sse_endpoint_replays_from_last_event_id(tmp_path: Path) -> None:
    app = create_app(FakeLLMClient([LLMResponse(True, text="done")]), tmp_path / "events.db")
    settings = get_settings()
    headers = {"Origin": settings.allowed_origins[0], "Authorization": f"Bearer {settings.app_session_token}"}
    with TestClient(app) as client:
        created = client.post("/api/chat", json={"message": "finish"}, headers=headers)
        task_id = created.json()["task_id"]
        for _ in range(30):
            detail = client.get(f"/api/tasks/{task_id}", headers=headers).json()
            if detail["state"] == "COMPLETED":
                break
            time.sleep(0.01)
        response = client.get(f"/api/tasks/{task_id}/events", headers={**headers, "Last-Event-ID": "2"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "id: 1" not in response.text
    assert "id: 3" in response.text
    assert "event: task_completed" in response.text

