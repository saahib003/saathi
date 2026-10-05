"""Conservative recursive redaction for audit data."""

import re
from typing import Any


_KEY_PATTERN = re.compile(r"(?i)(api[_-]?key|password|token|secret|credential)")
_VALUE_PATTERN = re.compile(r"(?i)((?:api[_-]?key|password|token|secret)\s*[=:]\s*)([^\s,;]+)")


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _KEY_PATTERN.search(str(key)) else redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return _VALUE_PATTERN.sub(r"\1[REDACTED]", value)
    return value

