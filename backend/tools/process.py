"""Bounded Windows subprocess execution."""

import os
import subprocess
import time
from dataclasses import dataclass

from backend.tools.base import ToolError, ToolResult


@dataclass(frozen=True)
class ProcessOutput:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    truncated: bool


def _cap(value: str, maximum: int) -> tuple[str, bool]:
    if len(value) <= maximum:
        return value, False
    return value[:maximum], True


def scrubbed_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        environment.pop(name, None)
    return environment


def run_argv(argv: list[str], cwd: str, timeout_seconds: float, output_max_chars: int) -> ToolResult:
    started = time.perf_counter()
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=scrubbed_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(process.pid)
        try:
            process.kill()
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""

    stdout, stdout_truncated = _cap(stdout or "", output_max_chars)
    stderr, stderr_truncated = _cap(stderr or "", output_max_chars)
    output = ProcessOutput(
        None if timed_out else process.returncode,
        stdout,
        stderr,
        round((time.perf_counter() - started) * 1000),
        stdout_truncated or stderr_truncated,
    )
    data = {
        "exit_code": output.exit_code,
        "stdout": output.stdout,
        "stderr": output.stderr,
        "duration_ms": output.duration_ms,
        "truncated": output.truncated,
    }
    if timed_out:
        return ToolResult(False, data=data, error=ToolError("CommandTimeout", "Command exceeded its timeout", retryable=True))
    if output.exit_code != 0:
        return ToolResult(False, data=data, error=ToolError("CommandExecutionError", f"Command exited with code {output.exit_code}"))
    return ToolResult(True, data=data)


def _kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
