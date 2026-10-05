# Project Overview

## Phase 8 status

Phase 0 assessed the empty repository. Phases 1–8 now provide the HTTP foundation, Gemini adapter, guarded filesystem tools, background agent loop, task persistence, approvals, cancellation, in-process events, authenticated SSE replay, the React task UI, risk-aware permission enforcement, bounded terminal/Git tools, and full scoped file operations.

## Goal

Build a local Windows laptop agent. A user types a natural-language request in a React UI; a FastAPI backend coordinates Gemini, validates proposed tool calls, applies policy, asks for approval when required, executes local tools, and reports structured results and progress.

The safety model is deliberately split:

- Gemini is the reasoning brain and proposes the next step.
- The local application is the hands and the guard.
- The policy engine, not the model, decides whether an action is allowed.
- Every action passes through one tool gateway and is auditable.

## Repository assessment

| Area | Finding | Consequence |
|---|---|---|
| Source tree | Only `SPEC.md` and `follow.md` exist at the repository root. | The implementation must be bootstrapped from the target layout in the spec. |
| Git | The directory is not currently a Git working tree. | Git history/status cannot be used until version control is initialized externally. |
| Backend | No `backend/`, Python package, requirements file, or `pyproject.toml`. | Phase 1 must establish the Python project and pinned dependencies. |
| Frontend | No `frontend/`, `package.json`, Vite config, or lockfile. | Phase 1 must establish the React/TypeScript/Vite shell. |
| Tests | No `tests/` directory or test configuration. | Tests must be introduced with the first product phase. |
| Configuration | No `.env`, `.env.example`, or application config exists. | Phase 1 must define configuration without committing secrets. |
| Gemini integration | `backend/llm/` contains the pinned SDK adapter and fake client. | The agent loop depends only on `LLMClient`; real credentials remain backend-only. |
| Existing material | `follow.md` is a second, older build prompt with overlapping architecture guidance. | `SPEC.md` remains the source of truth; `follow.md` should not be treated as implementation. |

## Environment assessment

- OS reported: Windows NT `10.0.26200.0`, AMD64. The WMI query was access-denied, so the exact Windows edition was not inferred.
- Python: `3.13.5` (`python` works; the `py` launcher is not installed).
- pip: `25.1.1`.
- Node.js: `v22.17.0`.
- npm: `10.9.2` via `npm.cmd`; PowerShell's `npm.ps1` is blocked by the current execution policy.
- Git executable: `2.50.0.windows.2`, but this directory is not a Git repository.
- Globally available Python packages include FastAPI `0.141.1`, uvicorn `0.52.4`, Pydantic `2.13.4`, SQLAlchemy `2.0.52`, pytest `8.4.2`, and python-dotenv `1.2.2`.
- No project dependency manifest exists, so global packages are observations only and must not be assumed as the project's reproducible environment.
- `google-genai` was not present in the inspected pip package list.
- No matching Gemini application key/config variable was found in the inspected environment-variable names. Values were never printed.

## Reusable decisions and constraints

The spec already fixes the major choices: Gemini Interactions API through an internal client, SQLite, background asyncio task per agent task, SSE, one `ToolGateway`, Windows-first behavior, localhost hardening, structured tools before raw shell, and no unnecessary infrastructure.

## How a sentence will become a laptop action

The future path is: React sends a message to FastAPI; the orchestrator starts `agent/loop.py`; the loop asks `LLMClient` for a response; a proposed tool call enters `tools/gateway.py`; the gateway validates arguments, consults policy, waits for approval if needed, executes a registered tool, records a redacted audit entry, and returns a structured result to the loop. The loop gives that result back to the model or finishes with a verified answer.

## Phase 0 boundary

Created in this phase: assessment and design documents only. No runtime, dependency, configuration, test, or product source files were created.
