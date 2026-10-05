# Laptop Agent

Local Windows laptop agent foundation. The intended system will let Gemini propose actions while the local policy engine and tool gateway decide whether those actions may run.

## Current status

Phase 10 is complete: the app now has bounded recovery, redacted audit traces, explicit SQLite memory with retrieval, bounded model context, and memory UI controls.

## Prerequisites

- Windows laptop
- Python 3.13+
- Node.js 22+
- npm

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
cd frontend
npm.cmd install
Copy-Item .env.example .env.local
```

Set `APP_SESSION_TOKEN` in `.env` to a random local value before using `/api/*`. If it is empty, the development process generates an in-memory token; this is convenient for tests but is not a persistent installation setup.

Set `MEMORY_ENABLED=false` to disable persistent memory retrieval and writes. Memory is never auto-saved; use the authenticated memory panel or `/api/memory` explicitly.

## Settings

The authenticated `/api/settings` endpoint and the frontend Settings panel expose human-only configuration: Gemini model, maximum agent steps, default terminal, browser and Computer Use flags, allowed roots, confirmation behavior, log retention, and memory enablement. The Gemini API key is intentionally neither accepted nor returned by this endpoint. Security-sensitive changes require the session token and may require a process restart when they affect tool construction.

## Run

Backend:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend, in another terminal:

```powershell
cd frontend
npm.cmd run dev
```

The frontend is currently a visual shell. The Gemini key belongs only in backend environment configuration and must never be placed in frontend files.

## Verify

```powershell
python -m pytest
cd frontend
npm.cmd run build
```

`GET http://127.0.0.1:8000/health` returns `{"status":"ok"}` without authentication. API routes reject missing tokens and unapproved origins.

## Security warning

This project is designed to control a real Windows laptop. Do not expose the server beyond localhost. Future tool results may send local file contents, command output, or screenshots to Gemini; this will be explained in the UI before those features are enabled. Never commit `.env` or API keys.

## Structure and documentation

- `main.py` — ASGI application factory and health endpoint
- `backend/config.py` — environment-backed settings
- `backend/llm/` — provider-neutral LLM interface, Gemini adapter, schemas, errors, and fake client
- `backend/tools/` — tool contracts, registry, gateway, and filesystem tools
- `backend/security/path_guard.py` — Windows-aware filesystem scope checks
- `backend/agent/` — task state, persistence, and background loop
- `backend/events/` — in-process task event bus
- `backend/policy/` — risk policy, permission storage, and argument hashing
- `backend/tools/process.py` — bounded subprocess execution and environment scrubbing
- `backend/tools/terminal.py` — PowerShell, pytest, and Git tools
- `backend/tools/filesystem.py` — filesystem tools including Recycle Bin deletion
- `frontend/src/services/api.ts` — authenticated REST and SSE client
- `scripts/gemini_smoke.py` — opt-in manual real-Gemini smoke test
- `backend/security/auth.py` — origin and session-token guard
- `backend/db/` — SQLite bootstrap and numbered migrations
- `frontend/` — React + TypeScript + Vite shell
- `tests/` — Phase 1 foundation/security tests
- `docs/` — phase docs including [Filesystem](docs/FILESYSTEM.md), [Terminal](docs/TERMINAL.md), [Permissions](docs/PERMISSIONS.md), and [Security](docs/SECURITY.md)
