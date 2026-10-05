"""Small logging setup with conservative secret redaction."""

import logging
import re


_SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|token|password|secret)([=:]\s*)([^\s,]+)")


def redact(message: str) -> str:
    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", message)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        record.args = ()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

