import asyncio
import json
import time
from pathlib import Path

import pytest

from backend.agent.loop import AgentLoop
from backend.agent.state import TaskState
from backend.agent.task_manager import TaskManager
from backend.config import get_settings
from backend.events.bus import EventBus
from backend.llm.client import LLMClient
from backend.llm.fake_client import FakeLLMClient
from backend.llm.schemas import LLMRequest, LLMResponse, ToolCall
from backend.security.path_guard import PathGuard
from backend.tools.filesystem import definitions
from backend.tools.gateway import ToolGateway
from backend.tools.registry import ToolRegistry
from main import create_app


def make_loop(tmp_path: Path, client: LLMClient, max_steps: int = 20) -> tuple[AgentLoop, TaskManager, EventBus]:
    manager = TaskManager(tmp_path / "agent.db")
    events = EventBus()
    registry = ToolRegistry()
    for definition in definitions(PathGuard([tmp_path])):
        registry.register(definition)
    return AgentLoop(manager, events, client, ToolGateway(registry), registry, max_steps), manager, events


def test_multi_step_task_executes_tool_and_finishes(tmp_path: Path) -> None:
    client = FakeLLMClient([
        LLMResponse(False, tool_calls=[ToolCall("call-1", "list_directory", {"path": str(tmp_path)})]),
        LLMResponse(True, text="Listed the directory."),
    ])
    loop, manager, events = make_loop(tmp_path, client)
    task = manager.create("List this directory")

    asyncio.run(loop.run_task(task.id))

    details = manager.details(task.id)
    assert details["state"] == TaskState.COMPLETED
    assert details["tool_calls"][0]["status"] == "COMPLETED"
    assert [event.type for event in events.history(task.id)] == ["task_started", "agent_thinking", "tool_requested", "tool_completed", "agent_thinking", "task_completed"]


async def resolve_pending(loop: AgentLoop, manager: TaskManager, task_id: str, decision: str) -> None:
    for _ in range(100):
        details = manager.details(task_id)
        if details["approvals"]:
            approval_id = details["approvals"][0]["id"]
            loop.resolve_approval(approval_id, decision == "approve")
            return
        await asyncio.sleep(0)
    raise AssertionError("approval was not created")


@pytest.mark.parametrize("decision,expected", [("approve", TaskState.COMPLETED), ("reject", TaskState.COMPLETED)])
def test_approval_suspend_resume_approve_and_reject(tmp_path: Path, decision: str, expected: TaskState) -> None:
    target = tmp_path / f"{decision}.txt"
    client = FakeLLMClient([
        LLMResponse(False, tool_calls=[ToolCall("call-1", "write_file", {"path": str(target), "content": "data"})]),
        LLMResponse(True, text="Finished after approval."),
    ])
    loop, manager, events = make_loop(tmp_path, client)
    task = manager.create("Write a file")

    async def scenario() -> None:
        running = asyncio.create_task(loop.run_task(task.id))
        await resolve_pending(loop, manager, task.id, decision)
        await running

    asyncio.run(scenario())

    assert manager.get(task.id).state is expected
    if decision == "approve":
        assert target.read_text(encoding="utf-8") == "data"
    else:
        assert not target.exists()
        assert any(event.type == "tool_failed" for event in events.history(task.id))


def test_tool_error_is_returned_to_model(tmp_path: Path) -> None:
    client = FakeLLMClient([
        LLMResponse(False, tool_calls=[ToolCall("call-1", "read_file", {"path": str(tmp_path / "missing.txt")})]),
        LLMResponse(True, text="The file was missing."),
    ])
    loop, manager, _ = make_loop(tmp_path, client)
    task = manager.create("Read a missing file")
    asyncio.run(loop.run_task(task.id))

    assert manager.get(task.id).state is TaskState.COMPLETED
    assert client.requests[1].input
    assert "FileNotFoundError" in json.dumps(client.requests[1].input)


def test_cancel_during_model_call_finishes_cancelled(tmp_path: Path) -> None:
    class BlockingClient(LLMClient):
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def generate(self, request: LLMRequest) -> LLMResponse:
            self.started.set()
            await self.release.wait()
            return LLMResponse(True, text="should not complete")

    client = BlockingClient()
    loop, manager, events = make_loop(tmp_path, client)
    task = manager.create("Cancel me")

    async def scenario() -> None:
        running = asyncio.create_task(loop.run_task(task.id))
        await client.started.wait()
        loop.cancel(task.id)
        client.release.set()
        await running

    asyncio.run(scenario())
    assert manager.get(task.id).state is TaskState.CANCELLED
    assert events.history(task.id)[-1].type == "task_cancelled"


def test_max_step_stop(tmp_path: Path) -> None:
    client = FakeLLMClient([LLMResponse(False, tool_calls=[])])
    loop, manager, events = make_loop(tmp_path, client, max_steps=1)
    task = manager.create("Never finish")
    asyncio.run(loop.run_task(task.id))
    assert manager.get(task.id).state is TaskState.FAILED
    assert events.history(task.id)[-1].type == "task_failed"


def test_illegal_state_transition_raises(tmp_path: Path) -> None:
    manager = TaskManager(tmp_path / "agent.db")
    task = manager.create("state")
    manager.transition(task.id, TaskState.CANCELLED)
    with pytest.raises(ValueError):
        manager.transition(task.id, TaskState.RUNNING)


def test_chat_and_task_api_start_background_task(tmp_path: Path) -> None:
    app = create_app(FakeLLMClient([LLMResponse(True, text="done")]), tmp_path / "api.db")
    settings = get_settings()
    headers = {"Origin": settings.allowed_origins[0], "Authorization": f"Bearer {settings.app_session_token}"}

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        created = client.post("/api/chat", json={"message": "Say done"}, headers=headers)
        assert created.status_code == 200
        task_id = created.json()["task_id"]
        for _ in range(20):
            detail = client.get(f"/api/tasks/{task_id}", headers=headers)
            if detail.json()["state"] == "COMPLETED":
                break
            time.sleep(0.01)
        assert detail.json()["final_response"] == "done"
