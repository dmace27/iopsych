"""Explicit, bounded local synthetic delivery operations; never an app startup hook."""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import re
from collections.abc import Sequence
from typing import NoReturn
from urllib.parse import urlsplit

from sqlalchemy.engine import URL, make_url

PROTECTED_PORTS = frozenset({3000, 8000, 8001, 5432})


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError("invalid arguments")


def _loopback(host: str | None) -> None:
    if host is None or "%" in host or not ipaddress.ip_address(host).is_loopback:
        raise ValueError("invalid local host")


def _port(port: int | None) -> None:
    if port is None or not 1024 <= port <= 65535 or port in PROTECTED_PORTS:
        raise ValueError("invalid local port")


def _target(acknowledged: str) -> URL:
    if any(key == "DATABASE_URL" or key.startswith("PG") for key in os.environ):
        raise ValueError("ambient database configuration")
    if (
        os.environ.get("AUTH_ENVIRONMENT") != "development"
        or os.environ.get("INVITE_ALLOW_SYNTHETIC_DEFINITIONS") != "true"
        or os.environ.get("INVITE_LOCAL_QUEUE_ENABLED") != "true"
    ):
        raise ValueError("local synthetic policy required")
    raw = os.environ["LOCAL_DELIVERY_DATABASE_URL"]
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.query
        or "#" in raw
        or not url.username
        or not url.database
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", url.database) is None
        or acknowledged != url.database
    ):
        raise ValueError("explicit database acknowledgement required")
    _loopback(url.host)
    _port(url.port)
    return url


def _execute(args: argparse.Namespace, url: URL) -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.invitations.worker import LocalDeliveryWorker, cleanup_deliveries

    worker_settings = None
    if args.action == "drain":
        from app.auth.config import AuthenticationSettings
        from app.invitations.config import InvitationSettings
        from app.invitations.local_delivery import LocalSmtpInvitationDelivery
        from app.invitations.queue import local_cipher

        _loopback(args.smtp_host)
        _port(args.smtp_port)
        authentication = AuthenticationSettings(_env_file=None)
        settings = InvitationSettings(_env_file=None)
        candidate = urlsplit(settings.candidate_base_url)
        _loopback(candidate.hostname)
        if candidate.username or candidate.password:
            raise ValueError("candidate URL credentials forbidden")
        _port(candidate.port)
        local_cipher(settings, authentication)
        adapter = LocalSmtpInvitationDelivery(
            enabled=True, host=args.smtp_host, port=args.smtp_port
        )
        worker_settings = (settings, authentication, adapter)
    elif args.smtp_port is not None or args.smtp_host != "127.0.0.1":
        raise ValueError("cleanup does not use SMTP")
    engine = create_engine(
        url,
        echo=False,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": "-c statement_timeout=10000 -c lock_timeout=3000",
        },
    )
    try:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        if worker_settings is None:
            return cleanup_deliveries(factory, limit=args.limit)
        return LocalDeliveryWorker(factory, *worker_settings).drain(limit=args.limit)
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    """Return 2 for rejected input, 1 for execution failure, and 0 for completion."""
    parser = _Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument("action", choices=("drain", "cleanup"))
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--ack-database", required=True)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--smtp-host", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int)
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    counts = {"attempted": 0, "cleaned": 0}
    status = 2
    try:
        args = parser.parse_args(argv)
        if not 1 <= args.limit <= 100:
            raise ValueError("invalid batch limit")
        url = _target(args.ack_database)
        status = 1
        count = _execute(args, url)
        counts["attempted" if args.action == "drain" else "cleaned"] = count
        status = 0
    except (Exception, KeyboardInterrupt):
        pass
    finally:
        logging.disable(previous_logging)
    print(json.dumps(counts, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
