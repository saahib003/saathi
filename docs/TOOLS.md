# Tools — Phase 3

## What exists

- `backend/tools/base.py` — risk levels, `ToolDefinition`, `ToolError`, and `ToolResult`.
- `backend/tools/registry.py` — unique registration, lookup, and Gemini schema export.
- `backend/tools/gateway.py` — the single execution choke point.
- `backend/tools/filesystem.py` — the first four structured tools.
- `backend/security/path_guard.py` — Windows path and credential protection.
- `backend/policy/engine.py` — minimal phase policy.

## Execution pipeline

1. Look up the tool by name.
2. Validate arguments with its Pydantic model.
3. Check every declared path before policy, so an unsafe path cannot become an approval prompt.
4. Ask the policy engine for ALLOW, ASK, or DENY.
5. For ALLOW, run the handler in a worker thread with a timeout.
6. Wrap success, failure, policy, and validation outcomes in `ToolResult`.
7. Add duration metadata and invoke the optional audit hook.

## Result contract

Every result has this shape:

```json
{
  "success": false,
  "data": null,
  "error": {
    "type": "ApprovalRequired",
    "message": "User approval is required before this tool can run",
    "retryable": false
  },
  "metadata": {"duration_ms": 0}
}
```

No executor returns a bare string. This gives the future agent loop enough information to explain failures honestly.

## Why structured tools

`write_file` expresses a narrow operation with typed fields rather than giving the model an unrestricted shell. This makes argument validation, path checks, approval UI, and tests concrete. Raw command execution is deferred to the terminal phase.

## Debugging

Start with `ToolGateway.execute()` and inspect the returned `ToolResult`. Add a temporary audit hook in a test rather than logging file contents or secrets. Tests in `tests/test_phase3.py` cover registration, schemas, path restrictions, approval behavior, and structured errors.

