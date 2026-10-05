"""Structured Windows terminal and Git tools."""

import sys

from pydantic import BaseModel, Field

from backend.security.path_guard import PathGuard
from backend.tools.base import RiskLevel, ToolDefinition
from backend.tools.process import run_argv


class CommandArguments(BaseModel):
    command: str = Field(min_length=1, max_length=20_000, description="Exact PowerShell command string")
    cwd: str = Field(description="Working directory inside an allowed root")


class WorkingDirectoryArguments(BaseModel):
    cwd: str = Field(description="Working directory inside an allowed root")


def run_command(arguments: CommandArguments, guard: PathGuard, timeout: float, output_max_chars: int):
    cwd = str(guard.check(arguments.cwd))
    return run_argv(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", arguments.command], cwd, timeout, output_max_chars)


def run_tests(arguments: WorkingDirectoryArguments, guard: PathGuard, timeout: float, output_max_chars: int):
    return run_argv([sys.executable, "-m", "pytest", "-q"], str(guard.check(arguments.cwd)), timeout, output_max_chars)


def git_status(arguments: WorkingDirectoryArguments, guard: PathGuard, timeout: float, output_max_chars: int):
    return run_argv(["git", "status", "--short"], str(guard.check(arguments.cwd)), timeout, output_max_chars)


def git_pull(arguments: WorkingDirectoryArguments, guard: PathGuard, timeout: float, output_max_chars: int):
    return run_argv(["git", "pull", "--ff-only"], str(guard.check(arguments.cwd)), timeout, output_max_chars)


def definitions(guard: PathGuard, timeout: float = 60, output_max_chars: int = 20_000) -> list[ToolDefinition]:
    return [
        ToolDefinition("run_command", "Run an exact PowerShell command in an allowed directory.", CommandArguments, RiskLevel.HIGH, lambda args: run_command(args, guard, timeout, output_max_chars), ("cwd",), timeout_seconds=timeout, path_guard=guard),
        ToolDefinition("run_tests", "Run pytest in an allowed project directory.", WorkingDirectoryArguments, RiskLevel.MEDIUM, lambda args: run_tests(args, guard, timeout, output_max_chars), ("cwd",), timeout_seconds=timeout, path_guard=guard),
        ToolDefinition("git_status", "Show concise Git status for an allowed project directory.", WorkingDirectoryArguments, RiskLevel.LOW, lambda args: git_status(args, guard, timeout, output_max_chars), ("cwd",), timeout_seconds=timeout, path_guard=guard),
        ToolDefinition("git_pull", "Fast-forward pull Git changes in an allowed project directory.", WorkingDirectoryArguments, RiskLevel.MEDIUM, lambda args: git_pull(args, guard, timeout, output_max_chars), ("cwd",), timeout_seconds=timeout, path_guard=guard),
    ]

