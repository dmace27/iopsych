"""Thread-safe fixed-window limits for invite creation and bearer-token access."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    """Describe whether a request is allowed and any required retry delay."""

    allowed: bool
    retry_after_seconds: int


@dataclass
class _Window:
    """Mutable counter guarded by the limiter lock."""

    expires_at: float
    count: int


class InMemoryRateLimiter:
    """Bound request bursts without retaining raw tokens or candidate PII."""

    def __init__(
        self, clock: Callable[[], float] = time.monotonic, *, maximum_keys: int = 10_000
    ) -> None:
        if maximum_keys < 1:
            raise ValueError("maximum_keys must be positive")
        self._maximum_keys = maximum_keys
        self._clock = clock
        self._windows: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        """Consume one request from a fixed window and report throttling state."""

        if limit < 1 or window_seconds < 1:
            raise ValueError("rate-limit policy values must be positive")
        now = self._clock()
        with self._lock:
            self._discard_expired(now)
            window = self._windows.get(key)
            if window is None:
                # Fail closed rather than evicting active keys and resetting budgets.
                if len(self._windows) >= self._maximum_keys:
                    retry_after = max(
                        1, math.ceil(min(w.expires_at for w in self._windows.values()) - now)
                    )
                    return RateLimitResult(allowed=False, retry_after_seconds=retry_after)
                self._windows[key] = _Window(expires_at=now + window_seconds, count=1)
                return RateLimitResult(allowed=True, retry_after_seconds=0)
            if window.count >= limit:
                retry_after = max(1, math.ceil(window.expires_at - now))
                return RateLimitResult(allowed=False, retry_after_seconds=retry_after)
            window.count += 1
            return RateLimitResult(allowed=True, retry_after_seconds=0)

    def _discard_expired(self, now: float) -> None:
        """Bound memory by deleting counters whose windows have elapsed."""

        expired = [key for key, window in self._windows.items() if now >= window.expires_at]
        for key in expired:
            del self._windows[key]
