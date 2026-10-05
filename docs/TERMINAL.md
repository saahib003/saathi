# Terminal — Phase 7

## What exists

`backend/tools/process.py` owns the Windows subprocess mechanics. `backend/tools/terminal.py` exposes four gateway tools:

- `run_command` — HIGH risk PowerShell command, always asks.
- `run_tests` — MEDIUM risk structured `python -m pytest -q` wrapper.
- `git_status` — LOW risk `git status --short` wrapper.
- `git_pull` — MEDIUM risk `git pull --ff-only` wrapper.

The agent never supplies an executable argv for `run_command`; it supplies a command string that is displayed exactly in approval UI and is passed to `powershell.exe -NoProfile -NonInteractive -Command`.

## Safety and lifecycle

1. The gateway validates arguments and the `PathGuard` checks the working directory.
2. Structured wrappers use explicit argv lists and never invoke a shell.
3. The child environment is copied and `GEMINI_API_KEY` is removed.
4. stdout/stderr are decoded with replacement for invalid bytes and capped by `TOOL_OUTPUT_MAX_CHARS`.
5. A timeout kills the whole Windows process tree with `taskkill /T /F`, then returns a structured timeout result.

## Result shape

Terminal data contains `exit_code`, `stdout`, `stderr`, `duration_ms`, and `truncated`. Non-zero exits and timeouts are failures returned as structured results so the agent can explain them.

## Risks

PowerShell is a powerful interpreter. A denylist is only a secondary defense; the HIGH-risk approval gate is the real control. The working directory is scoped, but commands can still affect other resources available to the user's account, so exact commands must be shown before approval.

## Debugging and study

Use harmless commands in a temporary directory. Inspect the argv, cwd, timeout, cap, and scrubbed environment in tests. Study `subprocess.Popen`, Windows process groups, `taskkill`, stdout/stderr pipes, and why shell-free argv is safer for structured tools.

