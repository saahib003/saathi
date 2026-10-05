# Security — Phase 6

## Why the agent is dangerous

The agent can eventually read local data, modify files, run commands, and control applications. Gemini output is untrusted; a convincing model response is not authorization.

## Current defenses

- One `ToolGateway` validates every call.
- Pydantic validates arguments before policy.
- `PathGuard` blocks traversal, system paths, credential paths, and Windows path tricks.
- Risk levels determine ALLOW, ASK, or DENY.
- High-risk tools always ask; critical tools deny by default.
- Permissions are human-created and scoped.
- Approval hashes bind authorization to exact arguments.
- API routes require localhost-origin checks and a bearer session token.

## Current limitations

The approval UI currently defaults to one-time approval and does not expose a scope picker. Prompt-injection taint rules, terminal controls, browser controls, and the final hardening pass arrive in later phases. The policy engine is the security boundary; system prompts are supporting guidance only.

## Study questions

Why is a shell denylist insufficient? Why must the gateway re-check an approval hash? Why can a permanent permission never authorize `run_command` or a critical action?

