"""Structured filesystem tools."""

import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from backend.security.path_guard import PathGuard
from backend.tools.base import RiskLevel, ToolDefinition
from send2trash import send2trash


class DirectoryArguments(BaseModel):
    path: str = Field(description="Directory path inside an allowed root")


class FileArguments(BaseModel):
    path: str = Field(description="File path inside an allowed root")


class WriteFileArguments(FileArguments):
    content: str = Field(description="Text content to write")


class SearchFilesArguments(BaseModel):
    root: str = Field(description="Directory to search inside an allowed root")
    pattern: str = Field(default="*", min_length=1, max_length=255, description="Filename glob pattern")
    max_results: int = Field(default=1000, ge=1, le=10_000)


class TwoPathArguments(BaseModel):
    source: str = Field(description="Existing file inside an allowed root")
    destination: str = Field(description="Destination file path inside an allowed root")


def list_directory(arguments: DirectoryArguments, guard: PathGuard) -> dict:
    path = guard.check(arguments.path)
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    entries = []
    for entry in sorted(path.iterdir(), key=lambda item: item.name.lower()):
        entries.append({"name": entry.name, "type": "directory" if entry.is_dir() else "file"})
    return {"path": str(path), "entries": entries}


def read_file(arguments: FileArguments, guard: PathGuard) -> dict:
    path = guard.check(arguments.path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return {"path": str(path), "content": path.read_text(encoding="utf-8")}


def create_directory(arguments: DirectoryArguments, guard: PathGuard) -> dict:
    path = guard.check(arguments.path)
    path.mkdir(parents=False, exist_ok=False)
    return {"path": str(path), "created": True}


def write_file(arguments: WriteFileArguments, guard: PathGuard) -> dict:
    path = guard.check(arguments.path)
    path.write_text(arguments.content, encoding="utf-8", newline="")
    return {"path": str(path), "bytes_written": len(arguments.content.encode("utf-8"))}


def search_files(arguments: SearchFilesArguments, guard: PathGuard) -> dict:
    root = guard.check(arguments.root)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    matches = []
    for candidate in root.rglob(arguments.pattern):
        try:
            resolved = guard.check(candidate)
        except ValueError:
            continue
        matches.append({"path": str(resolved), "type": "directory" if resolved.is_dir() else "file"})
        if len(matches) >= arguments.max_results:
            break
    return {"root": str(root), "pattern": arguments.pattern, "matches": matches, "truncated": len(matches) >= arguments.max_results}


def _file_path(raw_path: str, guard: PathGuard) -> Path:
    path = guard.check(raw_path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def _destination(raw_path: str, source: Path, guard: PathGuard) -> Path:
    destination = guard.check(raw_path)
    if destination.exists() and destination.is_dir():
        destination = guard.check(destination / source.name)
    if not destination.parent.exists():
        raise FileNotFoundError(str(destination.parent))
    return destination


def copy_file(arguments: TwoPathArguments, guard: PathGuard) -> dict:
    source = _file_path(arguments.source, guard)
    destination = _destination(arguments.destination, source, guard)
    shutil.copy2(source, destination)
    return {"source": str(source), "destination": str(destination), "copied": True}


def move_file(arguments: TwoPathArguments, guard: PathGuard) -> dict:
    source = _file_path(arguments.source, guard)
    destination = _destination(arguments.destination, source, guard)
    moved = Path(shutil.move(str(source), str(destination)))
    return {"source": str(source), "destination": str(moved), "moved": True}


def delete_file(arguments: FileArguments, guard: PathGuard) -> dict:
    path = _file_path(arguments.path, guard)
    send2trash(str(path))
    return {"path": str(path), "deleted": True, "destination": "recycle_bin"}


def file_metadata(arguments: FileArguments, guard: PathGuard) -> dict:
    path = guard.check(arguments.path)
    stat = path.stat()
    return {
        "path": str(path),
        "type": "directory" if path.is_dir() else "file",
        "size_bytes": stat.st_size if path.is_file() else None,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "created_at": datetime.fromtimestamp(stat.st_ctime, UTC).isoformat(),
    }


def definitions(guard: PathGuard) -> list[ToolDefinition]:
    return [
        ToolDefinition("list_directory", "List entries in an allowed directory.", DirectoryArguments, RiskLevel.LOW, lambda args: list_directory(args, guard), ("path",), path_guard=guard),
        ToolDefinition("read_file", "Read a UTF-8 text file in an allowed root.", FileArguments, RiskLevel.LOW, lambda args: read_file(args, guard), ("path",), path_guard=guard),
        ToolDefinition("create_directory", "Create one directory inside an allowed root.", DirectoryArguments, RiskLevel.MEDIUM, lambda args: create_directory(args, guard), ("path",), path_guard=guard),
        ToolDefinition("write_file", "Write UTF-8 text to a file in an allowed root.", WriteFileArguments, RiskLevel.MEDIUM, lambda args: write_file(args, guard), ("path",), path_guard=guard),
        ToolDefinition("search_files", "Recursively search for matching files inside an allowed directory.", SearchFilesArguments, RiskLevel.LOW, lambda args: search_files(args, guard), ("root",), path_guard=guard),
        ToolDefinition("copy_file", "Copy one file inside the allowed roots.", TwoPathArguments, RiskLevel.MEDIUM, lambda args: copy_file(args, guard), ("source", "destination"), path_guard=guard),
        ToolDefinition("move_file", "Move one file inside the allowed roots.", TwoPathArguments, RiskLevel.MEDIUM, lambda args: move_file(args, guard), ("source", "destination"), path_guard=guard),
        ToolDefinition("delete_file", "Send one file to the Windows Recycle Bin.", FileArguments, RiskLevel.HIGH, lambda args: delete_file(args, guard), ("path",), path_guard=guard),
        ToolDefinition("file_metadata", "Read metadata for an allowed file or directory.", FileArguments, RiskLevel.LOW, lambda args: file_metadata(args, guard), ("path",), path_guard=guard),
    ]
