import asyncio
from pathlib import Path

import pytest

from backend.llm.schemas import ToolCall
from backend.policy.engine import MinimalPolicy
from backend.security.path_guard import PathGuard, PathGuardError
from backend.tools.base import RiskLevel
from backend.tools.filesystem import definitions
from backend.tools.gateway import ToolGateway
from backend.tools.registry import ToolRegistry


def make_gateway(root: Path) -> ToolGateway:
    registry = ToolRegistry()
    for definition in definitions(PathGuard([root])):
        registry.register(definition)
    return ToolGateway(registry, MinimalPolicy())


def test_path_guard_allows_root_and_rejects_escape(tmp_path: Path) -> None:
    guard = PathGuard([tmp_path])
    assert guard.check(tmp_path / "file.txt").parent == tmp_path.resolve()
    with pytest.raises(PathGuardError):
        guard.check(tmp_path / ".." / "outside.txt")


@pytest.mark.parametrize("name", [".env", ".env.local", ".ssh", ".aws", ".git-credentials", "file.txt:secret", "CON", "notes. "])
def test_path_guard_rejects_sensitive_windows_paths(tmp_path: Path, name: str) -> None:
    with pytest.raises(PathGuardError):
        PathGuard([tmp_path]).check(tmp_path / name)


def test_path_guard_rejects_unc_and_system_paths(tmp_path: Path) -> None:
    guard = PathGuard([tmp_path])
    with pytest.raises(PathGuardError):
        guard.check(r"\\server\share\file.txt")
    with pytest.raises(PathGuardError):
        guard.check(r"C:\Windows\System32\config\SAM")


def test_tool_definitions_export_gemini_function_schemas(tmp_path: Path) -> None:
    registry = ToolRegistry()
    for definition in definitions(PathGuard([tmp_path])):
        registry.register(definition)
    schemas = registry.gemini_tools()
    assert {schema["name"] for schema in schemas} == {"list_directory", "read_file", "create_directory", "write_file", "search_files", "copy_file", "move_file", "delete_file", "file_metadata"}
    assert all(schema["type"] == "function" for schema in schemas)
    assert next(schema for schema in schemas if schema["name"] == "write_file")["parameters"]["required"] == ["path", "content"]


def test_low_risk_tools_execute_with_structured_result(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hello", encoding="utf-8")
    gateway = make_gateway(tmp_path)
    result = asyncio.run(gateway.execute(ToolCall("read", "read_file", {"path": str(tmp_path / "hello.txt")})))
    assert result.success is True
    assert result.data["content"] == "hello"
    assert result.error is None
    assert "duration_ms" in result.metadata


def test_medium_tools_return_approval_required_without_executing(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"
    gateway = make_gateway(tmp_path)
    result = asyncio.run(gateway.execute(ToolCall("write", "write_file", {"path": str(target), "content": "x"})))
    assert result.success is False
    assert result.error is not None
    assert result.error.type == "ApprovalRequired"
    assert not target.exists()


def test_path_guard_runs_before_approval(tmp_path: Path) -> None:
    gateway = make_gateway(tmp_path)
    result = asyncio.run(gateway.execute(ToolCall("secret", "write_file", {"path": str(tmp_path / ".env"), "content": "x"})))
    assert result.error is not None
    assert result.error.type == "PathDenied"


def test_invalid_arguments_never_reach_executor(tmp_path: Path) -> None:
    gateway = make_gateway(tmp_path)
    result = asyncio.run(gateway.execute(ToolCall("bad", "read_file", {"unexpected": "x"})))
    assert result.success is False
    assert result.error is not None
    assert result.error.type == "ValidationError"


def test_audit_hook_receives_redacted_contract(tmp_path: Path) -> None:
    calls = []
    registry = ToolRegistry()
    for definition in definitions(PathGuard([tmp_path])):
        registry.register(definition)
    gateway = ToolGateway(registry, audit_hook=lambda call, result: calls.append((call, result)))
    asyncio.run(gateway.execute(ToolCall("list", "list_directory", {"path": str(tmp_path)})))
    assert len(calls) == 1
    assert calls[0][1].to_dict()["metadata"]["duration_ms"] >= 0
