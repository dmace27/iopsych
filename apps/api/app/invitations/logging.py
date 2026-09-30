"""Credential and PII redaction before Python log records reach any handler."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

_CANDIDATE_TOKEN_PATH = re.compile(r"(/(?:v1/|api/)?candidate/invites/)[^/?\s\"']+")
_BEARER = re.compile(r"(?i)(bearer\s+)[^\s\"',}]+")
_SENSITIVE_VALUE = re.compile(
    r"(?i)([\"']?(?:authorization|cookie|set-cookie|token|jwt|secret|api[_-]?key)"
    r"[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")


def redact_log_text(value: str) -> str:
    """Preserve diagnostic context while removing URL credentials and secrets."""

    value = _CANDIDATE_TOKEN_PATH.sub(r"\1[REDACTED]", value)
    value = _BEARER.sub(r"\1[REDACTED]", value)
    value = _SENSITIVE_VALUE.sub(r"\1[REDACTED]", value)
    return _EMAIL.sub("[REDACTED_EMAIL]", value)


class CandidateInviteTokenFilter(logging.Filter):
    """Sanitize formatted messages and tracebacks without recording locals."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact after interpolation so credentials split across arguments are safe."""

        # Uvicorn's AccessFormatter reads the five positional fields itself;
        # preserve that contract rather than flattening the access record.
        if (
            record.name == "uvicorn.access"
            and isinstance(record.args, tuple)
            and len(record.args) == 5
        ):
            record.args = tuple(
                redact_log_text(value) if isinstance(value, str) else value for value in record.args
            )
            record.msg = redact_log_text(str(record.msg))
        else:
            record.msg = redact_log_text(record.getMessage())
            record.args = ()
        if record.exc_info:
            record.exc_text = redact_log_text(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        if record.stack_info:
            record.stack_info = redact_log_text(record.stack_info)
        return True


class _RedactingRecordFactory:
    """Wrap the current factory once, including future child/client loggers.

    Logger filters do not run for records propagated from a child logger. A
    factory covers that gap and retains any pre-existing custom record factory.
    Arbitrary structured extras and telemetry outside Python logging still need
    an explicit allowlist at their own integration boundary.
    """

    def __init__(self, previous: Callable[..., logging.LogRecord]) -> None:
        self.previous = previous
        self.redactor = CandidateInviteTokenFilter()

    def __call__(self, *args: Any, **kwargs: Any) -> logging.LogRecord:
        """Redact each newly created record before any handler can format it."""

        record = self.previous(*args, **kwargs)
        self.redactor.filter(record)
        return record


def install_invite_token_log_filter() -> None:
    """Install idempotent process-wide redaction while preserving logger setup."""

    factory = logging.getLogRecordFactory()
    if not isinstance(factory, _RedactingRecordFactory):
        logging.setLogRecordFactory(_RedactingRecordFactory(factory))
    # Keep an access-logger filter for manually constructed access records too.
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, CandidateInviteTokenFilter) for item in logger.filters):
        logger.addFilter(CandidateInviteTokenFilter())
