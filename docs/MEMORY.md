# Memory and context

Phase 10 separates three concepts:

- Conversation/task context is assembled for each model call by `ContextManager` and is not persistent memory.
- Persistent memory contains only explicit user-created facts through the authenticated `/api/memory` CRUD API or the UI memory panel.
- Audit records describe execution and are not memory.

`MemoryStore` keeps facts in SQLite, rejects credential-like key/value material, and never auto-saves tool output, model replies, or conversation messages. Retrieval is intentionally simple and local: relevant words in the task message are matched against memory content and tags, with a small result limit.

`MEMORY_ENABLED=false` disables retrieval and CRUD writes. The model still receives the task and tool context. This is an environment setting for Phase 10; human-only settings management is Phase 11.

The `ContextManager` adds a task-specific system message, relevant memories, recent messages, and the registered tool declarations. It limits recent messages and truncates tool results before sending them to Gemini. Context trimming does not delete the original task, tool call, or audit records.

Privacy guidance: do not save passwords, API keys, tokens, credentials, or secrets. The store rejects common credential-like assignments, and audit redaction remains an independent defense.
