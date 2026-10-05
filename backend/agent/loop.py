"""Bounded background agent loop with approvals, retries, and audit records."""

import asyncio
import json
import time
from typing import Any

from backend.agent.state import TaskState
from backend.agent.context import ContextManager
from backend.agent.task_manager import TaskManager
from backend.audit.store import AuditStore
from backend.events.bus import EventBus
from backend.llm.client import LLMClient
from backend.llm.schemas import LLMRequest, ToolCall
from backend.policy.hashing import arguments_hash
from backend.tools.base import ToolError, ToolResult
from backend.tools.gateway import ToolGateway
from backend.tools.registry import ToolRegistry


class ApprovalWaiter:
    def __init__(self) -> None:
        self._waiters: dict[str, asyncio.Future[bool]] = {}

    def register(self, approval_id: str) -> asyncio.Future[bool]:
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._waiters[approval_id] = future
        return future

    def resolve(self, approval_id: str, approved: bool) -> None:
        future = self._waiters.get(approval_id)
        if future is not None and not future.done():
            future.set_result(approved)

    def discard(self, approval_id: str) -> None:
        self._waiters.pop(approval_id, None)


class AgentLoop:
    def __init__(self, tasks: TaskManager, events: EventBus, llm: LLMClient, gateway: ToolGateway, registry: ToolRegistry, max_steps: int = 20, max_retries: int = 2, audit: AuditStore | None = None, context_manager: ContextManager | None = None) -> None:
        self.tasks, self.events, self.llm, self.gateway, self.registry = tasks, events, llm, gateway, registry
        self.max_steps, self.max_retries, self.audit = max_steps, max_retries, audit
        self.context_manager = context_manager
        self.approvals = ApprovalWaiter()
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._background: dict[str, asyncio.Task] = {}
        self._approval_calls: dict[str, ToolCall] = {}

    def _audit(self, task_id: str, kind: str, data: dict[str, Any], status: str, started: float, tool_call_id: str | None = None) -> None:
        if self.audit is not None:
            self.audit.record(task_id, kind, data, status, int((time.perf_counter() - started) * 1000), tool_call_id)

    def start(self, task_id: str) -> None:
        self._background[task_id] = asyncio.create_task(self.run_task(task_id))

    async def run_task(self, task_id: str) -> None:
        cancel_event = self._cancel_events.setdefault(task_id, asyncio.Event())
        try:
            task = self.tasks.get(task_id)
            self.tasks.transition(task_id, TaskState.PLANNING)
            self.events.emit(task_id, "task_started", {"message": task.user_message})
            self.events.emit(task_id, "agent_thinking", {"step": 0})
            self.tasks.transition(task_id, TaskState.RUNNING)
            context: list[dict[str, Any]] = [{"role": "user", "content": task.user_message}]
            for step in range(self.max_steps):
                if cancel_event.is_set() or self.tasks.get(task_id).cancel_requested:
                    return self._cancel(task_id)
                if step > 0:
                    self.events.emit(task_id, "agent_thinking", {"step": step})
                started = time.perf_counter()
                try:
                    request = self.context_manager.build(task, context) if self.context_manager else LLMRequest(input=context, tools=self.registry.gemini_tools())
                    response = await self.llm.generate(request)
                    self._audit(task_id, "model_call", {"step": step, "tool_calls": [call.name for call in response.tool_calls], "response": response.text or ""}, "completed", started)
                except Exception as exc:
                    self._audit(task_id, "model_call", {"step": step, "error": str(exc)}, "failed", started)
                    raise
                if cancel_event.is_set() or self.tasks.get(task_id).cancel_requested:
                    return self._cancel(task_id)
                if response.is_final:
                    finished = self.tasks.finish(task_id, TaskState.COMPLETED, response.text or "")
                    self._audit(task_id, "final_response", {"response": finished.final_response or ""}, "completed", started)
                    self.events.emit(task_id, "task_completed", {"response": finished.final_response})
                    return
                for call in response.tool_calls:
                    if cancel_event.is_set() or self.tasks.get(task_id).cancel_requested:
                        return self._cancel(task_id)
                    result = await self._execute_call(task_id, call, cancel_event)
                    context.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result.to_dict())})
                    if result.error and result.error.type == "UserRejected":
                        self.events.emit(task_id, "tool_failed", {"tool": call.name, "error": result.to_dict()})
                    elif result.success:
                        self.events.emit(task_id, "tool_completed", {"tool": call.name, "result": result.to_dict()})
                    else:
                        self.events.emit(task_id, "tool_failed", {"tool": call.name, "error": result.to_dict()})
            self.tasks.finish(task_id, TaskState.FAILED, "Agent reached the maximum step limit")
            self._audit(task_id, "final_response", {"response": "Agent reached the maximum step limit"}, "failed", time.perf_counter())
            self.events.emit(task_id, "task_failed", {"reason": "max_steps_reached"})
        except asyncio.CancelledError:
            if self.tasks.get(task_id).state not in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}:
                self._cancel(task_id)
        except Exception as exc:
            task = self.tasks.get(task_id)
            if task.state not in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}:
                self.tasks.finish(task_id, TaskState.FAILED, str(exc))
                self._audit(task_id, "final_response", {"response": str(exc)}, "failed", time.perf_counter())
                self.events.emit(task_id, "task_failed", {"reason": str(exc)})
        finally:
            self._background.pop(task_id, None)

    async def _execute_call(self, task_id: str, call: ToolCall, cancel_event: asyncio.Event) -> ToolResult:
        self.events.emit(task_id, "tool_requested", {"id": call.id, "tool": call.name, "arguments": call.arguments})
        database_call_id = self.tasks.add_tool_call(task_id, call.name, call.arguments)
        retries = self.registry.get(call.name).retry_policy
        retries = self.max_retries if retries is None else retries
        approved_hash: str | None = None
        result = ToolResult(False, error=ToolError("Unknown", "Tool did not return a result"))
        for attempt in range(retries + 1):
            started = time.perf_counter()
            result = await self.gateway.execute(call, approved_hash=approved_hash)
            if result.error and result.error.type == "ApprovalRequired":
                approved_hash = await self._wait_for_approval(task_id, call, database_call_id, cancel_event)
                if approved_hash is None:
                    cancelled = self.tasks.get(task_id).state == TaskState.CANCELLED
                    result = ToolResult(False, error=ToolError("Cancelled" if cancelled else "UserRejected", "Task was cancelled" if cancelled else "User rejected the tool call"))
                    break
                continue
            self._audit(task_id, "tool_call", {"tool": call.name, "arguments": call.arguments, "result": result.to_dict(), "attempt": attempt + 1, "approval": approved_hash is not None}, "completed" if result.success else "failed", started, database_call_id)
            if result.success or not result.error or not result.error.retryable or attempt >= retries:
                break
            self.events.emit(task_id, "tool_failed", {"tool": call.name, "error": result.to_dict(), "retrying": True, "attempt": attempt + 1})
        self.tasks.complete_tool_call(database_call_id, result)
        return result

    async def _wait_for_approval(self, task_id: str, call: ToolCall, database_call_id: str, cancel_event: asyncio.Event) -> str | None:
        self.tasks.transition(task_id, TaskState.WAITING_FOR_APPROVAL)
        approval_id = self.tasks.add_approval(task_id, database_call_id, arguments_hash(call.arguments))
        self._approval_calls[approval_id] = call
        waiter = self.approvals.register(approval_id)
        self.events.emit(task_id, "approval_required", {"approval_id": approval_id, "tool_call_id": call.id, "tool": call.name, "arguments": call.arguments})
        cancel_task = asyncio.create_task(cancel_event.wait())
        done, _ = await asyncio.wait({waiter, cancel_task}, return_when=asyncio.FIRST_COMPLETED)
        cancel_task.cancel()
        self.approvals.discard(approval_id)
        if cancel_event.is_set() or self.tasks.get(task_id).cancel_requested:
            self._cancel(task_id)
            return None
        approved = waiter.result() if waiter in done else False
        self.tasks.transition(task_id, TaskState.RUNNING)
        self.events.emit(task_id, "approval_resolved", {"approval_id": approval_id, "approved": approved})
        return arguments_hash(call.arguments) if approved else None

    def cancel(self, task_id: str) -> None:
        self.tasks.request_cancel(task_id)
        self._cancel_events.setdefault(task_id, asyncio.Event()).set()

    def resolve_approval(self, approval_id: str, approved: bool, scope_type: str = "one_time", scope_value: str | None = None) -> None:
        if approved and approval_id in self._approval_calls:
            call = self._approval_calls[approval_id]
            self.gateway.grant_permission(call.name, scope_type, scope_value)
        self.tasks.resolve_approval(approval_id, "approve" if approved else "reject", scope_type, scope_value)
        self.approvals.resolve(approval_id, approved)

    def _cancel(self, task_id: str) -> None:
        task = self.tasks.get(task_id)
        if task.state not in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}:
            self.tasks.finish(task_id, TaskState.CANCELLED, "Task cancelled")
            self.events.emit(task_id, "task_cancelled", {})
