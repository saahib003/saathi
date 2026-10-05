# Decisions

This file starts the decision record for the project. Decisions already made in `SPEC.md` are recorded here so future implementation choices remain traceable.

## D1 — Separate brain, hands, and guard

Decision: Gemini proposes; the policy engine authorizes; local executors act through one tool gateway.

Why: Model output is untrusted and must never be the security boundary.

Alternatives considered: Let the model invoke local functions directly; use a single permissive command runner.

Reason selected: Central validation, policy, approval, and audit create one enforceable choke point.

Trade-offs: More interfaces and plumbing, but much easier to test and reason about safely.

## D2 — Gemini Interactions API behind `LLMClient`

Decision: Use the official `google-genai` SDK and Gemini Interactions API inside `backend/llm/`; keep the model name in `GEMINI_MODEL`.

Why: This is the project specification's selected agent-oriented API and keeps provider details isolated.

Alternatives considered: Direct SDK calls from the loop; `generateContent`; another provider.

Reason selected: An internal interface permits fakes in tests and a future provider/API change without changing orchestration.

Trade-offs: The adapter must track a fast-changing SDK and official API; the SDK version must be pinned during Phase 2.

## D9 — Phase 2 Gemini API verification

Decision: Implement the current documented `google-genai` Interactions API shape: `client.interactions.create`, `interaction.steps`, `function_call` steps, and `output_text`, using `store=false` by default.

Why: The live official documentation is the authority for a fast-changing API and confirms that Interactions API is recommended for new projects.

Alternatives considered: Guess from older `generateContent` examples; use automatic function calling; rely on server-side interaction chaining.

Reason selected: It matches the project specification while preserving application-owned state and the gateway boundary.

Trade-offs: The adapter must resend context and re-specify request-scoped tools/instructions; automatic function calling is intentionally not used.


## D3 — Application-owned conversation state

Decision: Default to `GEMINI_STORE_INTERACTIONS=false`; SQLite and application context are the source of truth.

Why: Local files, screenshots, and task history should not be retained remotely by default.

Alternatives considered: Server-side interaction state as the default; stateless single-turn calls without local history.

Reason selected: It matches the privacy goal and the planned ContextManager.

Trade-offs: More context assembly and token management; current API behavior must be verified before implementing function calling or Computer Use.

## D4 — SQLite from the start of persistence

Decision: Use SQLite for tasks, tool calls, approvals, and later local state; choose one migration strategy in Phase 1.

Why: The app is local and needs durable task/approval state without extra infrastructure.

Alternatives considered: In-memory state; PostgreSQL; unstructured JSON files.

Reason selected: SQLite is local, transactional, inspectable, and sufficient for the stated scope.

Trade-offs: It is not a remote multi-user database and still needs disciplined migrations and async access patterns.

## D5 — Background asyncio task and in-process event bus

Decision: Run one background asyncio task per agent task and publish lifecycle events in-process.

Why: Approval suspension, cancellation, and live UI updates need non-blocking task execution.

Alternatives considered: Synchronous request processing; external queue/broker.

Reason selected: It meets the local-app scale without Redis or other infrastructure.

Trade-offs: Process restart recovery and horizontal scaling are limited; durable task state must be designed carefully.

## D6 — SSE for server-to-client events

Decision: Prefer SSE for task event streaming; approvals and cancellation remain POST requests.

Why: The stream is server-to-client, SSE reconnects simply, and it avoids unnecessary bidirectional protocol complexity.

Alternatives considered: WebSocket; client polling.

Reason selected: It matches the event direction and the spec's real-time transport decision.

Trade-offs: The client still needs ordinary authenticated REST requests for commands and reconnect/replay logic.

## Phase 0 repository decision

Decision: Treat `SPEC.md` as the single source of truth; do not merge `follow.md` into product code or treat its duplicated guidance as implementation.

Why: The repository contains no product implementation and the user explicitly directed this Phase 0 flow using `SPEC.md`.

Alternatives considered: Start from `follow.md`; reconcile both prompts by inventing a third specification.

Reason selected: This avoids scope drift and honors the explicit project contract.

Trade-offs: `follow.md` remains as historical/reference material and may become confusing until the project owner removes or archives it.

## D7 — Numbered SQL migrations

Decision: Manage SQLite schema changes with ordered SQL files and a `schema_migrations` table.

Why: Phase 1 needs a reproducible initialization path, while the application is small and local.

Alternatives considered: Alembic; creating tables ad hoc from Python startup code.

Reason selected: Plain SQL is easy to inspect and keeps the first migration layer small and educational.

Trade-offs: Future migrations must be immutable and carefully versioned; Alembic can be reconsidered only with an explicit decision.

## D8 — Session token delivery in Phase 1

Decision: Accept `APP_SESSION_TOKEN` from backend environment configuration; generate an in-memory development fallback when it is empty.

Why: The API must have a token guard immediately, while the persistent setup/token delivery workflow is not yet implemented.

Alternatives considered: Hard-coded token; no token until the full frontend setup exists; writing a token into source control.

Reason selected: It preserves the security boundary without creating a secret file or committing a secret.

Trade-offs: The fallback changes after process restart and is not a complete installation experience; a later setup flow must persist and deliver the frontend token safely.

## D10 — One guarded tool gateway

Decision: All Phase 3 tools register with `ToolRegistry` and execute only through `ToolGateway`.

Why: Validation, path safety, policy, timeouts, structured results, and audit hooks need one enforceable boundary.

Alternatives considered: Calling filesystem functions directly from the agent loop; giving each tool its own permission logic.

Reason selected: A single choke point preserves the brain/hands/guard split and makes later approval wiring local to the gateway.

Trade-offs: Every new tool must fit the registry and gateway contracts; this is intentional coordination overhead for safety.

## D11 — SQLite-backed task state with in-process active control

Decision: Persist tasks, tool calls, and approvals in SQLite while keeping active asyncio waiters and cancellation events in the process.

Why: The app needs durable inspection and a responsive approval loop without introducing a queue or broker.

Alternatives considered: Fully in-memory tasks; Redis-backed coordination; synchronous request-held loops.

Reason selected: SQLite is the existing local source of truth, and asyncio primitives match the single-process desktop runtime.

Trade-offs: Process restart recovery and multi-process coordination are not solved yet; later phases must handle recovery explicitly.

## D12 — Fetch-based SSE client

Decision: Use an authenticated `fetch()` stream for SSE instead of native `EventSource`.

Why: Native `EventSource` cannot attach the required bearer `Authorization` header. Fetch also lets the client send `Last-Event-ID` explicitly.

Alternatives considered: Put the session token in the URL; use cookies; use WebSocket.

Reason selected: Keep the token out of URLs and preserve the Phase 1 bearer-token boundary while retaining SSE's simple server-to-client model.

Trade-offs: The frontend owns a small SSE frame parser and reconnect loop instead of using the browser's native EventSource implementation.

## D13 — Canonical argument hash for approval binding

Decision: Store a SHA-256 hash of canonical JSON tool arguments with each approval and require the same hash at execution.

Why: An approval must authorize exactly what the human saw, not a later call with changed arguments.

Alternatives considered: Store only the tool name; compare raw JSON strings; trust the in-memory approval ID alone.

Reason selected: Canonicalization avoids key-order differences while the digest gives a small stable binding value.

Trade-offs: Any intentional argument change requires a new approval; hash metadata does not make sensitive arguments safe to log.

## D14 — Shell-free structured terminal tools

Decision: Structured test and Git tools use explicit argv lists; only `run_command` invokes PowerShell with `-NoProfile -NonInteractive -Command` and requires HIGH-risk approval.

Why: Structured tools reduce shell interpretation and make the operation visible and testable. A generic command tool remains available only as an explicitly approved escape hatch.

Alternatives considered: Use `shell=True` for every terminal operation; rely only on a command denylist.

Reason selected: The approval gate and shell-free argv are stronger, complementary controls; a denylist alone is easy to bypass.

Trade-offs: Wrapper coverage must grow for common workflows, and PowerShell commands remain powerful even after approval.

## D15 — Recycle Bin instead of permanent file deletion

Decision: Expose `delete_file` only as a Recycle Bin operation through `send2trash`; do not expose permanent deletion.

Why: The agent can make mistakes, and recoverability is the safer default for a personal laptop.

Alternatives considered: `Path.unlink()`; a permanent-delete flag; asking for confirmation before permanent deletion.

Reason selected: Removing the irreversible capability is stronger than relying on a confirmation dialog alone.

Trade-offs: Recycle Bin behavior depends on Windows volume support and is not suitable for every special filesystem object; those objects are outside this phase.

## D16 — Bounded recovery and redacted audit storage

Decision: Retry only errors explicitly marked retryable, with a global `AGENT_MAX_RETRIES` fallback and optional per-tool overrides. Store a redacted audit trace in SQLite and expose it with task details.

Why: Recovery must be finite and observable, while tool arguments and results may contain credentials or tokens.

## D17 — Explicit memory is separate from context

Decision: Persist only facts explicitly created through the memory API/UI. `ContextManager` retrieves a small relevant subset and trims recent tool results for each model call; disabling memory removes both retrieval and writes.

Why: Conversation history and execution context are not durable user memory. Automatic storage would retain sensitive or accidental content without a clear user decision.

## D18 — Settings are an authenticated human-only surface

Decision: Store only an allowlisted set of non-secret settings in SQLite and expose them through token-protected REST/UI. Reject unknown fields, never expose `GEMINI_API_KEY`, and never register settings operations as tools.

Why: The model must not be able to change its own permissions, roots, confirmation behavior, or feature gates.
