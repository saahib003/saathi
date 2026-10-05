"""The one execution choke point for all registered tools."""

import asyncio
import time
from collections.abc import Callable

from pydantic import ValidationError

from backend.llm.schemas import ToolCall
from backend.policy.engine import MinimalPolicy, PolicyDecision
from backend.policy.engine import PolicyEngine
from backend.policy.hashing import arguments_hash
from backend.security.path_guard import PathGuardError
from backend.tools.base import ToolError, ToolResult
from backend.tools.registry import ToolRegistry


class ToolGateway:
    def __init__(self, registry: ToolRegistry, policy: PolicyEngine | MinimalPolicy | None = None, audit_hook: Callable | None = None) -> None:
        self.registry = registry
        self.policy = policy or MinimalPolicy()
        self.audit_hook = audit_hook

    async def execute(self, call: ToolCall, *, approved_hash: str | None = None) -> ToolResult:
        started = time.perf_counter()
        try:
            definition = self.registry.get(call.name)
        except KeyError:
            return self._finish(call, ToolResult(False, error=ToolError("UnknownTool", "Tool is not registered")), started)

        try:
            arguments = definition.parameters.model_validate(call.arguments)
        except ValidationError as exc:
            return self._finish(call, ToolResult(False, error=ToolError("ValidationError", str(exc))), started)

        try:
            if definition.path_guard is not None:
                for field in definition.path_fields:
                    definition.path_guard.check(getattr(arguments, field))
        except PathGuardError as exc:
            return self._finish(call, ToolResult(False, error=ToolError("PathDenied", str(exc))), started)

        decision = self.policy.evaluate(definition, arguments)
        if decision is PolicyDecision.DENY:
            return self._finish(call, ToolResult(False, error=ToolError("PolicyDenied", "Policy denied this tool")), started)
        if decision is PolicyDecision.ASK and approved_hash is None:
            return self._finish(call, ToolResult(False, error=ToolError("ApprovalRequired", "User approval is required before this tool can run")), started)
        if decision is PolicyDecision.ASK and approved_hash != arguments_hash(call.arguments):
            return self._finish(call, ToolResult(False, error=ToolError("ApprovalMismatch", "Approval does not match these exact arguments")), started)

        try:
            data = await asyncio.wait_for(asyncio.to_thread(definition.handler, arguments), definition.timeout_seconds)
            result = data if isinstance(data, ToolResult) else ToolResult(True, data=data)
        except PathGuardError as exc:
            result = ToolResult(False, error=ToolError("PathDenied", str(exc)))
        except asyncio.TimeoutError:
            result = ToolResult(False, error=ToolError("ToolTimeout", "Tool exceeded its timeout", retryable=True))
        except Exception as exc:
            result = ToolResult(False, error=ToolError(type(exc).__name__, str(exc)))
        return self._finish(call, result, started)

    def grant_permission(self, tool_name: str, scope_type: str, scope_value: str | None = None) -> None:
        definition = self.registry.get(tool_name)
        if not isinstance(self.policy, PolicyEngine):
            raise ValueError("Permission storage is not configured")
        self.policy.grant_permission(definition, scope_type, scope_value)

    def _finish(self, call: ToolCall, result: ToolResult, started: float) -> ToolResult:
        metadata = {**result.metadata, "duration_ms": round((time.perf_counter() - started) * 1000)}
        finished = ToolResult(result.success, result.data, result.error, metadata)
        if self.audit_hook:
            self.audit_hook(call, finished)
        return finished
