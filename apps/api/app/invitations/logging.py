"""Access-log redaction for bearer invite tokens embedded in API paths."""

from __future__ import annotations

import logging
import re

_CANDIDATE_TOKEN_PATH = re.compile(r"(/v1/candidate/invites/)[^/?\s]+")


class CandidateInviteTokenFilter(logging.Filter):
    """Replace raw invite path segments before Uvicorn formats a log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact path-like string arguments while retaining useful route context."""

        if isinstance(record.args, tuple):
            record.args = tuple(
                _redact_path(argument) if isinstance(argument, str) else argument
                for argument in record.args
            )
        elif isinstance(record.args, dict):
            record.args = {
                key: _redact_path(value) if isinstance(value, str) else value
                for key, value in record.args.items()
            }
        if isinstance(record.msg, str):
            record.msg = _redact_path(record.msg)
        return True


def install_invite_token_log_filter() -> None:
    """Install one process-wide filter on Uvicorn's access logger."""

    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, CandidateInviteTokenFilter) for item in access_logger.filters):
        access_logger.addFilter(CandidateInviteTokenFilter())


def _redact_path(value: str) -> str:
    """Preserve endpoint shape while removing the reusable bearer credential."""

    return _CANDIDATE_TOKEN_PATH.sub(r"\1[REDACTED]", value)
