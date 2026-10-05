# Saathi workflow

This document explains what happens when a user sends a request to Saathi. It uses simple words and describes the code that currently exists through Phase 11.

## The short version

```text
User
  ↓
React frontend
  ↓  REST request with session token + origin
FastAPI API
  ↓
TaskManager creates a task
  ↓
AgentLoop starts in the background
  ↓
ContextManager prepares the information for Gemini
  ↓
Gemini chooses: final answer OR a registered tool call
  ↓
ToolGateway validates, checks the path and policy, and may ask for approval
  ↓
Tool executor performs the action
  ↓
Structured result returns to AgentLoop
  ↓
Gemini receives the result and continues or answers
  ↓
SQLite audit + SSE events + React timeline
```

There is currently one agent loop per task. The tools are separate workers that the agent can request through the `ToolGateway`. Gemini does not directly access Windows, files, PowerShell, or SQLite.

## What happens to a normal question

Example question:

> Create a file named `saahib` on my Desktop.

1. The React app sends `POST /api/chat` to the backend.
2. The API checks the browser origin and session token.
3. `TaskManager` creates a task in SQLite and returns its `task_id` immediately.
4. `AgentLoop` runs that task in a background asyncio task, so the HTTP request does not stay open while the agent works.
5. The loop emits events such as `task_started` and `agent_thinking`. The frontend receives them through the SSE endpoint.
6. `ContextManager` prepares the model request. It includes the task, recent messages, relevant explicit memories, instructions, and all registered tool descriptions. Long tool results are trimmed before being sent.
7. Gemini decides that it needs a filesystem tool. It returns a structured function call, for example `write_file`, with a path and file content.
8. `AgentLoop` sends that call to `ToolGateway`. It never calls the filesystem function directly.
9. `ToolGateway` validates the arguments, checks that the Desktop path is inside an allowed root, evaluates the risk policy, and asks the user for approval when required.
10. If the user approves the exact arguments, the filesystem executor writes the file. If the user rejects, the model receives a structured `UserRejected` result instead.
11. The result is saved in the task trace and appended to the next model context.
12. Gemini can now confirm success, recover from an error, or request another tool.
13. The final answer is saved in SQLite and shown in the React timeline and audit trace.

## The main components

| Component | Simple responsibility | Connected to |
|---|---|---|
| React frontend | Chat box, task list, approvals, memory, settings, trace viewer | FastAPI REST and SSE endpoints |
| `LocalApiGuard` | Checks allowed browser origin and bearer token | Every `/api` request |
| FastAPI `main.py` | Receives requests and exposes API endpoints | TaskManager, AgentLoop, MemoryStore, SettingsStore |
| `TaskManager` | Stores task state, tool calls, approvals, and final responses | SQLite |
| `AgentLoop` | Runs the reasoning/action cycle for one task | ContextManager, Gemini client, ToolGateway, EventBus |
| `ContextManager` | Chooses and limits what Gemini sees on each step | MemoryStore, ToolRegistry, LLM request |
| `GeminiClient` | Sends the model request and parses final text/function calls | Google Gemini SDK |
| `ToolRegistry` | Holds the tools Gemini is allowed to request | Filesystem and terminal definitions |
| `ToolGateway` | Single safety checkpoint for every tool call | Validation, PathGuard, PolicyEngine, executor, audit |
| `PolicyEngine` | Decides ALLOW, ASK, or DENY based on risk and permissions | ToolDefinition and PermissionStore |
| `PathGuard` | Prevents access outside configured allowed roots | Filesystem and terminal tools |
| `EventBus` | Publishes live task events | SSE endpoint and React timeline |
| `MemoryStore` | Stores only facts explicitly created by the user | SQLite and ContextManager |
| `SettingsStore` | Stores human-only non-secret settings | SQLite and settings API/UI |
| `AuditStore` | Stores redacted model/tool/final-response history | SQLite and task trace viewer |

## The agent and its connection to tools

The agent is the `AgentLoop`. It is not a separate process and it is not a collection of multiple autonomous agents. Each user task gets one background `AgentLoop` instance.

The connection is:

```text
AgentLoop
  ├── asks Gemini what to do
  ├── sends Gemini's function call to ToolGateway
  ├── waits for approval when the policy says ASK
  ├── gives the structured result back to Gemini
  └── repeats until final answer, failure, cancellation, or max steps
```

The agent knows tools only through the schemas exported by `ToolRegistry`. It does not import the implementation functions directly.

## Current tool catalogue

### Filesystem tools

All filesystem paths pass through `PathGuard`. The tool receives validated Pydantic arguments and returns a structured result.

| Tool | What it does | Risk / usual policy |
|---|---|---|
| `list_directory` | Lists files and folders in a directory | LOW / usually ALLOW |
| `read_file` | Reads a UTF-8 text file | LOW / usually ALLOW |
| `create_directory` | Creates one directory | MEDIUM / ASK |
| `write_file` | Writes UTF-8 content to a file | MEDIUM / ASK |
| `search_files` | Recursively searches for a filename pattern | LOW / usually ALLOW |
| `copy_file` | Copies one file to another allowed location | MEDIUM / ASK |
| `move_file` | Moves one file to another allowed location | MEDIUM / ASK |
| `delete_file` | Sends a file to the Windows Recycle Bin | HIGH / ASK |
| `file_metadata` | Reads file or directory type, size, and timestamps | LOW / usually ALLOW |

`delete_file` does not permanently delete files. It uses the Recycle Bin through `send2trash`.

### Terminal and Git tools

All working directories pass through `PathGuard`. Process execution is bounded by a timeout and output limit.

| Tool | What it does | Risk / usual policy |
|---|---|---|
| `run_command` | Runs the exact requested PowerShell command | HIGH / ASK every time |
| `run_tests` | Runs `python -m pytest -q` in a selected project directory | MEDIUM / ASK |
| `git_status` | Runs `git status --short` | LOW / usually ALLOW |
| `git_pull` | Runs `git pull --ff-only` | MEDIUM / ASK |

`run_command` is the broadest tool and is intentionally protected by approval. Structured tools such as `run_tests` and `git_status` are preferred because their behavior is easier to see and control.

## What happens inside the ToolGateway

Every tool call follows this order:

```text
1. Find the tool by name
2. Validate arguments with its Pydantic model
3. Check every declared path with PathGuard
4. Ask PolicyEngine for ALLOW, ASK, or DENY
5. If ASK, pause the task and show approval in the UI
6. If approved, verify the exact argument hash
7. Execute with timeout and output limits
8. Convert the result to ToolResult
9. Retry only explicitly retryable failures, within the retry limit
10. Save a redacted audit record
11. Return the result to AgentLoop
```

A denied or rejected action is not silently changed or bypassed. The structured error goes back to Gemini so it can explain what happened or choose another safe path.

## Task states

```text
PENDING
  → PLANNING
  → RUNNING
  → WAITING_FOR_APPROVAL  (when a human decision is needed)
  → RUNNING
  → COMPLETED or FAILED or CANCELLED
```

The task can also be cancelled while it is running or waiting for approval. The frontend gets state changes through SSE and can reload the complete state from `GET /api/tasks/{task_id}`.

## Memory, context, and settings

These are separate things:

- **Context** is temporary information assembled for one Gemini request.
- **Memory** is a user-created fact saved explicitly through the memory UI/API. Tool output and conversations are not automatically saved as memory.
- **Settings** are human-only configuration. They are not tools, are not included in Gemini's tool list, and do not expose the Gemini API key.
- **Audit** is a redacted execution record used to explain what happened. It is not presented as user memory.

`MEMORY_ENABLED=false` turns off memory retrieval and new memory writes while leaving ordinary task context available.

## How the frontend sees progress

The frontend uses two kinds of communication:

- REST: create tasks, load task details, cancel tasks, resolve approvals, manage memory, and manage settings.
- SSE: receive live events such as `task_started`, `agent_thinking`, `tool_requested`, `approval_required`, `tool_completed`, `task_completed`, and `task_failed`.

The trace viewer reads the redacted audit entries attached to the task. It can show model calls, tool attempts, retry status, durations, and the final response without exposing credential values.

## Where to look in the code

| Concern | Main file or directory |
|---|---|
| API and app wiring | `main.py` |
| Agent cycle | `backend/agent/loop.py` |
| Context construction | `backend/agent/context.py` |
| Task persistence | `backend/agent/task_manager.py` |
| Gemini boundary | `backend/llm/gemini_client.py` |
| Tool contracts | `backend/tools/base.py` |
| Tool list | `backend/tools/registry.py` |
| Safety checkpoint | `backend/tools/gateway.py` |
| Filesystem actions | `backend/tools/filesystem.py` |
| Terminal/Git actions | `backend/tools/terminal.py` |
| Path protection | `backend/security/path_guard.py` |
| Permissions | `backend/policy/engine.py` and `backend/policy/permissions.py` |
| Memory | `backend/memory/store.py` |
| Settings | `backend/settings.py` |
| Audit | `backend/audit/store.py` and `backend/audit/redaction.py` |
| Live events | `backend/events/bus.py` |
| Frontend | `frontend/src/main.tsx` and `frontend/src/services/api.ts` |

## Important safety idea

Gemini suggests. The local application decides.

Gemini can request `write_file`, `run_command`, or another registered tool, but it cannot execute that action by itself. The local gateway, path guard, policy engine, approval flow, timeout, and audit trail are the controls that decide whether and how the action runs.
