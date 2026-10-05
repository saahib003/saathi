# API — Phase 1

Phase 4 adds task, approval, and cancellation endpoints. SSE is intentionally deferred to Phase 5.

## Server

The backend must bind to `127.0.0.1`. `APP_HOST` is configuration for the eventual launcher, but a deployment must not change the security requirement to `0.0.0.0`.

## Authentication and origin

`GET /health` is public and returns:

```json
{"status": "ok"}
```

Every `/api/*` request must include both:

```http
Origin: http://localhost:5173
Authorization: Bearer <APP_SESSION_TOKEN>
```

Origins are read from `ALLOWED_ORIGINS`. Missing or invalid tokens return `401`; an origin not in the allow-list returns `403`. The guard also covers future SSE paths because it checks the `/api` path at the ASGI boundary.

## Current route surface

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | None | Liveness check |
| POST | `/api/chat` | Token + origin | Create and schedule an agent task |
| GET | `/api/tasks` | Token + origin | List tasks with traces |
| GET | `/api/tasks/{id}` | Token + origin | Inspect one task |
| POST | `/api/tasks/{id}/cancel` | Token + origin | Request cancellation |
| POST | `/api/approvals/{id}` | Token + origin | `{ "decision": "approve" | "reject", "scope": "one_time" | "scoped" | "permanent", "scope_value": "..." }` |
| GET | `/api/tasks/{id}/events` | Token + origin | Authenticated SSE event stream |

The event stream sends `id`, `event`, and JSON `data` frames. Clients send `Last-Event-ID` to replay events after that cursor.

## Database initialization

Application startup applies numbered SQL files from `backend/db/migrations/` to the configured SQLite database. `schema_migrations` records applied versions. Phase 4 adds `tasks`, `tool_calls`, and `approvals`.
