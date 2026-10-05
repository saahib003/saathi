import asyncio
import os
import sys
from pathlib import Path

from backend.policy.engine import PolicyEngine
from backend.security.path_guard import PathGuard
from backend.tools.base import ToolResult
from backend.tools.gateway import ToolGateway
from backend.tools.process import run_argv
from backend.tools.registry import ToolRegistry
from backend.tools.terminal import definitions
from backend.llm.schemas import ToolCall


def test_process_output_is_capped(tmp_path: Path) -> None:
    result = run_argv([sys.executable, "-c", "print('x' * 100)"], str(tmp_path), 5, 12)
    assert result.success is True
    assert result.data["truncated"] is True
    assert len(result.data["stdout"]) == 12


def test_gemini_key_is_scrubbed_from_child_environment(tmp_path: Path) -> None:
    previous = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = "secret-value"
    try:
        result = run_argv([sys.executable, "-c", "import os; print(os.getenv('GEMINI_API_KEY', 'MISSING'))"], str(tmp_path), 5, 200)
    finally:
        if previous is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = previous
    assert result.success is True
    assert "secret-value" not in result.data["stdout"]
    assert "MISSING" in result.data["stdout"]


def test_timeout_kills_process_tree(tmp_path: Path) -> None:
    result = run_argv([sys.executable, "-c", "import time; time.sleep(30)"], str(tmp_path), 0.2, 200)
    assert result.success is False
    assert result.error is not None
    assert result.error.type == "CommandTimeout"
    assert result.data["exit_code"] is None


def test_terminal_tools_are_registered_with_risk_and_gateway(tmp_path: Path) -> None:
    registry = ToolRegistry()
    for definition in definitions(PathGuard([tmp_path]), timeout=5, output_max_chars=200):
        registry.register(definition)
    gateway = ToolGateway(registry, PolicyEngine())

    approval = asyncio.run(gateway.execute(ToolCall("command", "run_command", {"command": "Write-Output safe", "cwd": str(tmp_path)})))
    assert approval.error is not None
    assert approval.error.type == "ApprovalRequired"

    status = asyncio.run(gateway.execute(ToolCall("status", "git_status", {"cwd": str(tmp_path)})))
    assert isinstance(status, ToolResult)
    assert status.data["exit_code"] is not None
    assert set(status.data) == {"exit_code", "stdout", "stderr", "duration_ms", "truncated"}

