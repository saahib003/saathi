import asyncio
from pathlib import Path

from backend.policy.engine import PolicyEngine
from backend.policy.hashing import arguments_hash
from backend.security.path_guard import PathGuard
from backend.tools.base import RiskLevel
from backend.tools.filesystem import (
    FileArguments,
    SearchFilesArguments,
    TwoPathArguments,
    copy_file,
    delete_file,
    file_metadata,
    move_file,
    search_files,
)
from backend.tools.gateway import ToolGateway
from backend.tools.registry import ToolRegistry
from backend.llm.schemas import ToolCall


def test_search_files_is_recursive_and_bounded(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (nested / "b.py").write_text("b", encoding="utf-8")
    (nested / "c.txt").write_text("c", encoding="utf-8")
    result = search_files(SearchFilesArguments(root=str(tmp_path), pattern="*.py", max_results=1), PathGuard([tmp_path]))
    assert len(result["matches"]) == 1
    assert result["truncated"] is True


def test_copy_move_and_metadata_use_temp_files_only(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    copied = tmp_path / "copied.txt"
    moved = tmp_path / "moved.txt"
    source.write_text("content", encoding="utf-8")
    guard = PathGuard([tmp_path])

    assert copy_file(TwoPathArguments(source=str(source), destination=str(copied)), guard)["copied"] is True
    assert copied.read_text(encoding="utf-8") == "content"
    assert move_file(TwoPathArguments(source=str(copied), destination=str(moved)), guard)["moved"] is True
    assert not copied.exists()
    metadata = file_metadata(FileArguments(path=str(moved)), guard)
    assert metadata["size_bytes"] == 7
    assert metadata["type"] == "file"


def test_delete_sends_file_to_recycle_bin(tmp_path: Path) -> None:
    target = tmp_path / "temporary.log"
    target.write_text("temporary", encoding="utf-8")
    result = delete_file(FileArguments(path=str(target)), PathGuard([tmp_path]))
    assert result["deleted"] is True
    assert result["destination"] == "recycle_bin"
    assert not target.exists()


def test_delete_requires_high_risk_approval(tmp_path: Path) -> None:
    registry = ToolRegistry()
    for definition in __import__("backend.tools.filesystem", fromlist=["definitions"]).definitions(PathGuard([tmp_path])):
        registry.register(definition)
    gateway = ToolGateway(registry, PolicyEngine())
    target = tmp_path / "approval.log"
    target.write_text("temporary", encoding="utf-8")
    call = ToolCall("delete", "delete_file", {"path": str(target)})
    pending = asyncio.run(gateway.execute(call))
    assert pending.error is not None
    assert pending.error.type == "ApprovalRequired"
    approved = asyncio.run(gateway.execute(call, approved_hash=arguments_hash(call.arguments)))
    assert approved.success is True
    assert not target.exists()

