"""Circuit breaker for fault isolation.

After ``failure_threshold`` consecutive failures the breaker opens and rejects
calls fast (failing fast protects the caller and gives the downstream time to
recover). Once ``reset_timeout`` elapses it lets a single probe through
(half-open); success closes it again, failure re-opens it.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from .errors import CircuitOpenError


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 10.0,
        half_open_max: int = 1,
        now: Optional[Callable[[], float]] = None,
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max = half_open_max
        self._now = now or time.time
        self.failures = 0
        self.state = self.CLOSED
        self.opened_at = 0.0
        self._half_open_calls = 0

    def _allow(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if self._now() - self.opened_at >= self.reset_timeout:
                self.state = self.HALF_OPEN
                self._half_open_calls = 0
                return True
            return False
        # HALF_OPEN
        return self._half_open_calls < self.half_open_max

    def call(self, fn: Callable[[], object]) -> object:
        if not self._allow():
            raise CircuitOpenError(f"circuit open (failures={self.failures})")
        if self.state == self.HALF_OPEN:
            self._half_open_calls += 1
        try:
            result = fn()
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result

    def _on_failure(self) -> None:
        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            self.opened_at = self._now()
            return
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = self.OPEN
            self.opened_at = self._now()

    def _on_success(self) -> None:
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
        self.failures = 0
