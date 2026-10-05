CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_value TEXT,
    created_at TEXT NOT NULL
);

ALTER TABLE approvals ADD COLUMN arguments_hash TEXT;
ALTER TABLE approvals ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'one_time';
ALTER TABLE approvals ADD COLUMN scope_value TEXT;

