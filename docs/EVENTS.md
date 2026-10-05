# Events and SSE — Phase 5

## Why SSE

The agent sends progress from the server to the UI: thinking, tool requests, approvals, tool results, and task completion. The UI sends commands such as chat, approval, and cancel through ordinary authenticated `POST` requests. Server-Sent Events (SSE) matches that one-way stream, reconnects naturally, and is simpler than a bidirectional WebSocket for this boundary.

## Event contract

Every event has a monotonic ID per task:

```json
{
  "id": 4,
  "task_id": "...",
  "type": "approval_required",
  "timestamp": "2026-09-30T12:00:00+00:00",
  "payload": {"tool": "write_file", "arguments": {}}
}
```

The SSE frame repeats the ID and event type:

```text
id: 4
event: approval_required
data: {"id":4,"task_id":"...",...}

```

## Replay and reconnect

The client sends `Last-Event-ID` when reconnecting. The server first yields events after that ID from the in-process event history, then subscribes to new events. The task API remains the source for durable state; SSE is a live view, not the database.

## Authentication

The existing `/api` ASGI guard checks the allowed `Origin` and bearer session token before the stream is opened. The frontend uses authenticated `fetch()` streaming rather than native `EventSource`, because native `EventSource` cannot attach a bearer header.

## Alternatives and limitations

WebSocket would support client-to-server messages on one connection, but those messages are already ordinary REST commands here. The Phase 5 event history is process-local; durable replay after a server restart is deferred until the persistence/observability work is expanded.

## Debugging

Inspect `backend/events/bus.py`, then `GET /api/tasks/{id}/events`. In the browser, the event reader stores the last received ID and reconnects with it after a stream error. Tests cover monotonic IDs and replay after a cursor.

