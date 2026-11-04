"""Scheduler entry point for bounded cross-organization retention cleanup."""

import argparse
import json
import math
import sys
import time
from collections.abc import Sequence
from typing import NoReturn

from app.database.session import create_database_engine, create_session_factory
from app.privacy.config import PrivacySettings
from app.privacy.service import PrivacyService


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.exit(2, "Retention arguments invalid; use --help for supported bounds.\n")


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = _SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--drain", action="store_true", help="Opt in to bounded multiple batches")
    parser.add_argument("--max-batches", type=int, help="Positive maximum number of batch attempts")
    parser.add_argument(
        "--max-seconds", type=float, help="Finite positive elapsed budget for starting batches"
    )
    args = parser.parse_args(argv)
    if args.drain:
        if (
            args.max_batches is None
            or args.max_batches <= 0
            or args.max_seconds is None
            or not math.isfinite(args.max_seconds)
            or args.max_seconds <= 0
        ):
            parser.error("Drain requires both positive bounds")
    elif args.max_batches is not None or args.max_seconds is not None:
        parser.error("Bounds require --drain")
    return args


def main(argv: Sequence[str] = ()) -> None:
    """Run bounded batches without interpreting no progress as an empty backlog."""

    args = _arguments(argv)
    attempted = 0
    completed = 0
    anonymized = 0
    reason = "single_batch"
    failed = False
    engine = None
    started = time.monotonic()
    try:
        settings = PrivacySettings()
        engine = create_database_engine()
        factory = create_session_factory(engine)
        while True:
            if args.drain and time.monotonic() - started >= args.max_seconds:
                reason = "time_budget"
                break
            attempted += 1
            with factory() as session:
                result = PrivacyService(session, settings).run_retention()
                count = len(result.anonymized_assessment_ids)
                completed += 1
                anonymized += count
            if not args.drain:
                break
            if count == 0:
                reason = "no_progress"
                break
            if attempted >= args.max_batches:
                reason = "max_batches"
                break
    except Exception:
        failed = True
        reason = "error"
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                failed = True
                reason = "error"
    if args.drain or failed:
        print(
            json.dumps(
                {
                    "attempted_batches": attempted,
                    "completed_batches": completed,
                    "assessments_anonymized": anonymized,
                    "stop_reason": reason,
                },
                sort_keys=True,
            )
        )
    else:
        print(f"Retention complete: {anonymized} assessments anonymized")
    if failed:
        print("Retention failed; no further batches started.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
