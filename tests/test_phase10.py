from pathlib import Path

import pytest

from backend.agent.context import ContextManager
from backend.agent.task_manager import TaskManager
from backend.memory.store import MemoryStore
from backend.tools.registry import ToolRegistry
from backend.config import get_settings
from main import create_app
from fastapi.testclient import TestClient


def test_memory_crud_and_retrieval(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "agent.db")
    item = store.create("The backend project lives in saathi", ["project"])
    assert store.relevant("Where is the backend project?")[0]["id"] == item["id"]
    assert store.list()[0]["content"].startswith("The backend")
    store.delete(item["id"])
    assert store.list() == []


def test_memory_rejects_credential_material(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "agent.db")
    with pytest.raises(ValueError, match="credential"):
        store.create("api_key=do-not-store")


def test_memory_disabled_is_empty_and_does_not_write(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "agent.db", enabled=False)
    assert store.list() == []
    assert store.relevant("anything") == []
    with pytest.raises(ValueError, match="disabled"):
        store.create("remember this")


def test_context_manager_trims_tool_results_and_includes_relevant_memory(tmp_path: Path) -> None:
    database = tmp_path / "agent.db"
    memories = MemoryStore(database)
    memories.create("The project uses a local SQLite database")
    tasks = TaskManager(database)
    task = tasks.create("Tell me about the SQLite project")
    manager = ContextManager(memories, ToolRegistry(), max_tool_chars=20)
    request = manager.build(task, [{"role": "user", "content": task.user_message}, {"role": "tool", "content": "x" * 100}])
    assert "SQLite" in request.input[1]["content"]
    assert len(request.input[-1]["content"]) == 20
    assert request.system_instruction is not None


def test_memory_api_is_authenticated_and_crud(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "agent.db")
    settings = get_settings()
    headers = {"Origin": settings.allowed_origins[0], "Authorization": f"Bearer {settings.app_session_token}"}
    with TestClient(app) as client:
        created = client.post("/api/memory", headers=headers, json={"content": "The API test project is local"})
        assert created.status_code == 200
        memory_id = created.json()["id"]
        assert client.get("/api/memory", headers=headers).json()[0]["id"] == memory_id
        assert client.delete(f"/api/memory/{memory_id}", headers=headers).status_code == 200
