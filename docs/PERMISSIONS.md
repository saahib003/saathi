# Permissions — Phase 6

## Decision model

The policy engine evaluates a registered tool's declared risk and the human-created permission store:

| Risk | Default | Permanent permission |
|---|---|---|
| LOW | ALLOW inside guarded paths | Allowed |
| MEDIUM | ASK | Allowed when explicitly granted |
| HIGH | ASK every time | Never allowed |
| CRITICAL | DENY | Never allowed by default |

`CONFIRMATION_BEHAVIOR=always` forces even low-risk calls through approval. The model cannot change this setting.

## Permission scopes

- `one_time`: the approval authorizes the exact current call only.
- `scoped`: persists a tool plus a human-provided path/project scope.
- `permanent`: persists a tool permission and is limited to LOW/MEDIUM tools.

The Phase 5 UI sends `one_time` by default. The API accepts `scope` and `scope_value` for future settings/UI controls.

## Argument binding

Arguments are canonicalized with sorted JSON keys and hashed with SHA-256. The approval record stores that hash. On execution, the gateway compares the approved hash with the current call. Changed arguments produce `ApprovalMismatch` and cannot reuse the approval.

## Storage and debugging

Permissions live in SQLite in the `permissions` table. Approval metadata lives in `approvals`. Inspect structured task details through `GET /api/tasks/{id}`; never log secrets or raw credentials while debugging.

