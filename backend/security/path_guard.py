"""Windows-aware filesystem scope and sensitive-path checks."""

import os
from pathlib import Path


class PathGuardError(ValueError):
    """Raised when a requested path is unsafe or outside configured roots."""


_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class PathGuard:
    def __init__(self, allowed_roots: list[str | Path]) -> None:
        if not allowed_roots:
            raise ValueError("At least one allowed filesystem root is required")
        self.allowed_roots = [self._resolve_root(Path(root)) for root in allowed_roots]

    def check(self, raw_path: str | Path) -> Path:
        value = str(raw_path)
        self._reject_lexical_tricks(value)
        candidate = Path(value).expanduser().resolve(strict=False)
        self._reject_sensitive(candidate)
        if not any(self._is_relative_to(candidate, root) for root in self.allowed_roots):
            raise PathGuardError("Path is outside the configured allowed roots")
        return candidate

    @staticmethod
    def _resolve_root(root: Path) -> Path:
        resolved = root.expanduser().resolve(strict=False)
        if not resolved.exists():
            raise ValueError(f"Allowed root does not exist: {root}")
        return resolved

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        candidate = os.path.normcase(str(path))
        base = os.path.normcase(str(root))
        try:
            return Path(candidate).is_relative_to(Path(base))
        except AttributeError:
            return candidate == base or candidate.startswith(base + os.sep)

    @staticmethod
    def _reject_lexical_tricks(value: str) -> None:
        lowered = value.lower()
        if lowered.startswith((r"\\", "//", "\\\\.", "\\\\?")):
            raise PathGuardError("UNC and device paths are not allowed")
        if len(value) > 2 and ":" in value[2:]:
            raise PathGuardError("Alternate data streams are not allowed")
        for part in value.replace("/", "\\").split("\\"):
            if part and part.rstrip(" .") != part:
                raise PathGuardError("Trailing dots and spaces are not allowed")
            stem = part.rstrip(" .").split(".", maxsplit=1)[0].upper()
            if stem in _RESERVED_NAMES:
                raise PathGuardError("Windows reserved names are not allowed")

    @staticmethod
    def _reject_sensitive(path: Path) -> None:
        parts = {part.lower() for part in path.parts}
        sensitive_names = {".ssh", ".aws", ".git-credentials", "credentials", "cookies", "login data"}
        if any(part.startswith(".env") for part in parts) or parts.intersection(sensitive_names):
            raise PathGuardError("Credential and secret-bearing paths are not readable or writable")

        blocked_roots = [
            Path(os.environ.get("WINDIR", r"C:\Windows")),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        ]
        normalized = os.path.normcase(str(path))
        for root in blocked_roots:
            root_text = os.path.normcase(str(root.resolve(strict=False)))
            if normalized == root_text or normalized.startswith(root_text + os.sep):
                raise PathGuardError("Windows system directories are blocked")
