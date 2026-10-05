# Observability — Phase 9

## Audit trail

`backend/audit/` stores redacted audit entries in SQLite. Entries cover:

- model call summaries and responses;
- each tool attempt, arguments, result, retry status, and duration;
- approval outcomes;
- the final task response.

Raw secrets are never stored. Sensitive dictionary keys and key/value patterns such as API keys, tokens, passwords, and secrets are replaced before persistence.

## Trace view

The task detail API returns tool calls, approvals, and audit entries. The React task timeline consumes the task event stream and replays it after reconnect, providing the live trace view. SQLite audit data remains available through task inspection after the live stream closes.

## Limitations

Audit records are local SQLite rows, not a distributed logging system. Retention cleanup and richer redaction checks remain part of the final hardening phase. Summaries intentionally avoid storing complete model prompts or large tool outputs.

## Debugging questions

What is the difference between an event and an audit entry? Which data is redacted before storage? How can a retry be distinguished from a second independent tool request?

