-- Phase 1 proves migration wiring. Feature tables arrive in their specified phases.
CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

