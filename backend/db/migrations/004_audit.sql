CREATE TABLE IF NOT EXISTS audit_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    kind TEXT NOT NULL,
    tool_call_id TEXT,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);

