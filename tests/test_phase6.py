import asyncio
from pathlib import Path

from backend.db.database import initialize_database
from backend.policy.engine import PolicyDecision, PolicyEngine
from backend.policy.permissions import PermissionScope, PermissionStore
from backend.security.path_guard import PathGuard
from backend.tools.base import RiskLevel, ToolDefinition
from backend.tools.filesystem import definitions
from backend.tools.gateway import ToolGateway
from backend.tools.registry import ToolRegistry
from backend.llm.schemas import ToolCall


def make_policy(tmp_path: Path) -> PolicyEngine:
    database_path = tmp_path / "policy.db"
    initialize_database(database_path)
    return PolicyEngine(PermissionStore(database_path))


def test_medium_permission_is_scoped_and_persistent(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    write_definition = next(item for item in definitions(PathGuard([tmp_path])) if item.name == "write_file")
    arguments = type("Args", (), {"model_dump": lambda self: {"path": str(tmp_path / "project" / "a.txt")}})()

    assert policy.evaluate(write_definition, arguments) is PolicyDecision.ASK
    policy.grant_permission(write_definition, PermissionScope.SCOPED, str(tmp_path / "project"))
    assert policy.evaluate(write_definition, arguments) is PolicyDecision.ALLOW
    other = type("Args", (), {"model_dump": lambda self: {"path": str(tmp_path / "other" / "a.txt")}})()
    assert policy.evaluate(write_definition, other) is PolicyDecision.ASK


def test_high_always_asks_and_critical_denies(tmp_path: Path) -> None:
    policy = make_policy(tmp_path)
    high = ToolDefinition("danger", "danger", type("Args", (), {}), RiskLevel.HIGH, lambda _: None)
    critical = ToolDefinition("critical", "critical", type("Args", (), {}), RiskLevel.CRITICAL, lambda _: None)
    empty = type("Args", (), {"model_dump": lambda self: {}})()
    assert policy.evaluate(high, empty) is PolicyDecision.ASK
    assert policy.evaluate(critical, empty) is PolicyDecision.DENY


def test_approval_hash_mismatch_cannot_authorize_different_arguments(tmp_path: Path) -> None:
    initialize_database(tmp_path / "gateway.db")
    registry = ToolRegistry()
    for definition in definitions(PathGuard([tmp_path])):
        registry.register(definition)
    gateway = ToolGateway(registry, PolicyEngine(PermissionStore(tmp_path / "gateway.db")))
    target = tmp_path / "approved.txt"
    call = ToolCall("call-1", "write_file", {"path": str(target), "content": "approved"})

    mismatch = asyncio.run(gateway.execute(call, approved_hash="wrong"))
    assert mismatch.error is not None
    assert mismatch.error.type == "ApprovalMismatch"
    assert not target.exists()

    from backend.policy.hashing import arguments_hash
    success = asyncio.run(gateway.execute(call, approved_hash=arguments_hash(call.arguments)))
    assert success.success is True
    assert target.read_text(encoding="utf-8") == "approved"

