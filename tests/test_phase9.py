import asyncio
from pathlib import Path

from pydantic import BaseModel

from backend.agent.loop import AgentLoop
from backend.agent.task_manager import TaskManager
from backend.audit.store import AuditStore
from backend.events.bus import EventBus
from backend.llm.schemas import LLMResponse, ToolCall
from backend.tools.base import RiskLevel, ToolDefinition, ToolError, ToolResult
from backend.tools.gateway import ToolGateway
from backend.tools.registry import ToolRegistry


class EmptyArgs(BaseModel):
    pass


class FakeLLM:
    def __init__(self, responses: list[LLMResponse]):
        self.responses = iter(responses)

    async def generate(self, _request):
        return next(self.responses)


def test_retry_then_give_up_is_bounded_and_audited(tmp_path: Path) -> None:
    calls = 0

    def flaky(_args):
        nonlocal calls
        calls += 1
        return ToolResult(False, error=ToolError("Temporary", "try again", retryable=True))

    registry = ToolRegistry()
    registry.register(ToolDefinition("flaky", "A flaky test tool", EmptyArgs, RiskLevel.LOW, flaky, retry_policy=1))
    database = tmp_path / "agent.db"
    tasks = TaskManager(database)
    task = tasks.create("try the flaky tool")
    loop = AgentLoop(
        tasks, EventBus(), FakeLLM([LLMResponse(False, tool_calls=[ToolCall("call-1", "flaky", {})]), LLMResponse(True, "I could not complete that safely.")]),
        ToolGateway(registry), registry, max_retries=5, audit=AuditStore(database)
    )
    asyncio.run(loop.run_task(task.id))
    assert calls == 2
    assert tasks.get(task.id).final_response == "I could not complete that safely."
    entries = AuditStore(database).list_for_task(task.id)
    assert len([entry for entry in entries if entry["kind"] == "tool_call"]) == 2


def test_audit_redacts_secrets(tmp_path: Path) -> None:
    database = tmp_path / "agent.db"
    tasks = TaskManager(database)
    task = tasks.create("redact")
    AuditStore(database).record(task.id, "tool_call", {"api_key": "secret-key", "password": "pw", "message": "token=abc"}, "failed")
    data = AuditStore(database).list_for_task(task.id)[0]["data"]
    assert data == {"api_key": "[REDACTED]", "password": "[REDACTED]", "message": "token=[REDACTED]"}
    assert "secret-key" not in str(data)
    assert "abc" not in str(data)


def test_task_details_exposes_trace(tmp_path: Path) -> None:
    database = tmp_path / "agent.db"
    tasks = TaskManager(database)
    task = tasks.create("trace")
    AuditStore(database).record(task.id, "final_response", {"response": "done"}, "completed")
    assert tasks.details(task.id)["audit"][0]["kind"] == "final_response"
