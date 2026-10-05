CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    user_message TEXT NOT NULL,
    state TEXT NOT NULL,
    final_response TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_json TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    tool_call_id TEXT NOT NULL REFERENCES tool_calls(id),
    decision TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

