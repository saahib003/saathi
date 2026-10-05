# Agent Loop — Phase 4

## What it is

`backend/agent/loop.py` runs one user task as a background asyncio task. Each step builds context, asks the `LLMClient` for either a final answer or tool calls, routes every call through `ToolGateway`, returns results to the model, and stops at completion, failure, cancellation, approval suspension, or the maximum step count.

```text
PENDING -> PLANNING -> RUNNING
                         |
                         +-> WAITING_FOR_APPROVAL -> RUNNING
                         +-> COMPLETED / FAILED / CANCELLED
```

## Request-to-action example

1. `POST /api/chat` creates task `t1` with state `PENDING`.
2. The background loop moves it through `PLANNING` to `RUNNING` and emits `task_started`.
3. Gemini returns `create_directory(path=...)` as a `ToolCall`.
4. The loop calls `ToolGateway.execute(call)`; the gateway returns `ApprovalRequired` for this medium-risk tool.
5. The loop stores an approval, moves to `WAITING_FOR_APPROVAL`, and emits the exact tool and arguments.
6. The approval endpoint resolves the waiter. Approval resumes the loop with the exact call; rejection becomes a `UserRejected` result.
7. The structured result is appended to context. The next model response can finish the task or recover from the result.

## Cancellation

`AgentLoop.cancel()` sets both a persisted cancellation flag and an asyncio event. The loop checks cancellation before each step, after model generation, before each tool, and while waiting for approval. This ensures an approval wait can be interrupted without executing the tool.

## Errors and limits

Tool errors are data returned to the model, not hidden exceptions. Unexpected loop errors fail the task honestly. `max_steps` is configured by `AGENT_MAX_STEPS` and is never controlled by the model.

## Debugging and study questions

Start with `run_task()`, then follow `_execute_call()`, `TaskManager`, and `ToolGateway`. Understand why the loop does not import the Gemini SDK, why rejected actions become model-visible results, and why an approval must resume the exact original arguments.

