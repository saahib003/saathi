"""ASGI entry point for the Phase 1 foundation."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.agent.loop import AgentLoop
from backend.agent.context import ContextManager
from backend.agent.task_manager import TaskManager
from backend.audit.store import AuditStore
from backend.config import get_settings
from backend.db.database import initialize_database
from backend.events.bus import EventBus
from backend.llm.client import LLMClient
from backend.llm.gemini_client import GeminiClient
from backend.llm.unavailable import UnavailableLLMClient
from backend.logging_config import configure_logging
from backend.memory.store import MemoryStore
from backend.policy.engine import PolicyEngine
from backend.policy.permissions import PermissionStore
from backend.security.auth import LocalApiGuard
from backend.security.path_guard import PathGuard
from backend.settings import SettingsStore
from backend.tools.filesystem import definitions
from backend.tools.gateway import ToolGateway
from backend.tools.registry import ToolRegistry
from backend.tools.terminal import definitions as terminal_definitions


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class ApprovalRequest(BaseModel):
    decision: Literal["approve", "reject"]
    scope: Literal["one_time", "scoped", "permanent"] = "one_time"
    scope_value: str | None = None


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5_000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gemini_model: str | None = None
    agent_max_steps: int | None = None
    default_terminal: str | None = None
    browser_enabled: bool | None = None
    allowed_roots: list[str] | None = None
    confirmation_behavior: Literal["ask", "always"] | None = None
    log_retention_days: int | None = None
    memory_enabled: bool | None = None
    computer_use_enabled: bool | None = None


def create_app(llm_client: LLMClient | None = None, database_path: Path | None = None) -> FastAPI:
    settings = get_settings()
    settings.ensure_session_token()
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db_path = database_path or settings.sqlite_path()
        initialize_database(db_path)
        tasks = TaskManager(db_path)
        events = EventBus()
        registry = ToolRegistry()
        for definition in definitions(PathGuard(settings.allowed_roots)):
            registry.register(definition)
        for definition in terminal_definitions(PathGuard(settings.allowed_roots), settings.tool_timeout_seconds, settings.tool_output_max_chars):
            registry.register(definition)
        if llm_client is not None:
            model_client = llm_client
        elif settings.gemini_api_key and settings.gemini_model:
            model_client = GeminiClient(settings)
        else:
            model_client = UnavailableLLMClient()
        app.state.tasks = tasks
        app.state.events = events
        policy = PolicyEngine(PermissionStore(db_path), settings.confirmation_behavior)
        memories = MemoryStore(db_path, settings.memory_enabled)
        settings_store = SettingsStore(db_path, settings)
        app.state.settings_store = settings_store
        app.state.policy = policy
        app.state.agent_loop = AgentLoop(
            tasks,
            events,
            model_client,
            ToolGateway(registry, policy),
            registry,
            settings.agent_max_steps,
            settings.agent_max_retries,
            AuditStore(db_path),
            ContextManager(memories, registry),
        )
        app.state.memories = memories
        logging.getLogger(__name__).info("Laptop Agent started on %s:%s", settings.app_host, settings.app_port)
        yield

    app = FastAPI(title="Laptop Agent", version="0.1.0", lifespan=lifespan)

    def service() -> AgentLoop:
        return app.state.agent_loop

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/chat")
    async def chat(request: ChatRequest) -> dict[str, str]:
        task = app.state.tasks.create(request.message)
        service().start(task.id)
        return {"task_id": task.id}

    @app.get("/api/tasks")
    async def list_tasks() -> list[dict]:
        return [app.state.tasks.details(task.id) for task in app.state.tasks.list()]

    @app.get("/api/memory")
    async def list_memory() -> list[dict]:
        return app.state.memories.list()

    @app.get("/api/settings")
    async def get_app_settings() -> dict:
        return app.state.settings_store.get()

    @app.put("/api/settings")
    async def update_app_settings(payload: SettingsUpdate) -> dict:
        changes = payload.model_dump(exclude_none=True)
        try:
            values = app.state.settings_store.update(changes)
            if "memory_enabled" in changes:
                app.state.memories.enabled = changes["memory_enabled"]
            if "agent_max_steps" in changes:
                service().max_steps = changes["agent_max_steps"]
            if "confirmation_behavior" in changes:
                app.state.policy.confirmation_behavior = changes["confirmation_behavior"]
            return values
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/memory")
    async def create_memory(payload: MemoryRequest) -> dict:
        try:
            return app.state.memories.create(payload.content, payload.tags)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/memory/{memory_id}")
    async def delete_memory(memory_id: str) -> dict[str, str]:
        try:
            app.state.memories.delete(memory_id)
            return {"id": memory_id, "status": "deleted"}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str) -> dict:
        try:
            return app.state.tasks.details(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str) -> dict:
        try:
            app.state.tasks.get(task_id)
            service().cancel(task_id)
            return app.state.tasks.details(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc

    @app.post("/api/approvals/{approval_id}")
    async def resolve_approval(approval_id: str, request: ApprovalRequest) -> dict[str, str]:
        try:
            task_id, _ = app.state.tasks.get_approval(approval_id)
            service().resolve_approval(approval_id, request.decision == "approve", request.scope, request.scope_value)
            return {"approval_id": approval_id, "task_id": task_id, "decision": request.decision}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}/events")
    async def task_events(task_id: str, request: Request) -> StreamingResponse:
        try:
            app.state.tasks.get(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        try:
            after_id = int(request.headers.get("last-event-id", "0"))
        except ValueError:
            after_id = 0

        async def stream():
            terminal = {"task_completed", "task_failed", "task_cancelled"}
            async for event in app.state.events.subscribe(task_id, after_id):
                yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(event.to_dict())}\n\n"
                if event.type in terminal:
                    break

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LocalApiGuard, settings=settings)
    return app


app = create_app()
