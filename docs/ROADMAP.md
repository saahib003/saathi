# Roadmap

This roadmap is intentionally limited to work after Phase 0. No product implementation has been started.

## Phase 0 — Assess and design — complete

- Inspected the repository and environment.
- Recorded the assessment, proposed architecture, fixed decisions, assumptions, risks, and implementation order.
- Created this document plus `PROJECT_OVERVIEW.md`, `ARCHITECTURE.md`, and `DECISIONS.md`.

## Milestone 1 — Safe core agent

### Phase 1 — Foundation and localhost security — complete

Created the FastAPI shell, configuration, redacted logging, localhost/origin/token protection, SQLite initialization and numbered migration strategy, React/Vite shell, and the first health/security tests.

### Phase 2 — Gemini client — complete

Pinned and integrated `google-genai` through `LLMClient`; added configuration, retries, application-owned history input, error mapping, and a fake client. Verified the current official Gemini Interactions API and function-calling documentation before coding.

### Phase 3 — Tools, gateway, and first filesystem tools — complete

Added tool contracts, registry, gateway, Windows-aware path guard, four structured filesystem tools, and the minimal policy/approval hook.

### Phase 4 — Orchestrator, tasks, and events — complete

Added the explicit agent loop, task state machine, SQLite task/tool-call/approval tables, cancellation, approval suspension/resumption, event bus, and authenticated task APIs. SSE remains Phase 5.

### Phase 5 — SSE UI and approvals — complete

Added the SSE explainer, authenticated event stream, task timeline, approval dialog, cancellation, and reconnect/replay behavior. Frontend production build passes.

### Phase 6 — Policy and permissions — complete

Implemented risk levels, ALLOW/ASK/DENY, one-time/scoped/permanent permissions, approval argument hashes, and security documentation.

### Phase 7 — Terminal — complete

Added PowerShell command execution and structured test/Git wrappers with output caps, timeouts, process-tree termination, and environment scrubbing.

## Later milestones

- Phase 8–9: full filesystem operations, recovery, audit trail, and observability.
- Phase 10–11: explicit memory, context management, and human-only settings.
- Phase 12–13: Playwright browser automation and Windows UI Automation.
- Phase 14–15: MCP integration and opt-in Computer Use preview.
- Phase 16: security pass, full tests, documentation review, learning guide, and troubleshooting guide.

### Phase 8 — Full filesystem — complete

Added recursive search, copy, move, Recycle Bin deletion, and file metadata with temporary-directory tests.

### Phase 9 — Error recovery and audit trail — complete

Added bounded retry policies, retryable error classification, redacted audit records, task trace API output, and a frontend trace viewer.

### Phase 10 — Memory and context manager — complete

Added explicit memory CRUD with credential-like content rejection, relevance retrieval, `MEMORY_ENABLED`, bounded context construction, and a memory viewer in the frontend.

### Phase 11 — Settings — complete

Added authenticated human-only settings CRUD and UI for model, execution, browser/Computer Use flags, allowed roots, confirmation, retention, and memory. Unknown or secret fields are rejected and settings are not registered as tools.

## Ordering constraints

- Do not add a major technology without its short explainer before implementation.
- Verify current official Gemini, Playwright, MCP, and Computer Use documentation at the phase where each is implemented.
- Keep destructive behavior confined to temp directories, mocks, and fakes in automated tests.
- Stop after each phase and wait for explicit continuation.
