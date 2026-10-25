"""Retry policy with exponential backoff and jitter.

Wraps a callable and re-runs it while the raised exception is considered
retryable, pausing with ``base_delay * backoff ** attempt`` (clamped to
``max_delay``) plus a little jitter so many clients don't thunder-herd the
provider in lockstep.
"""

from __future__ import annotations

import random
from typing import Callable, Optional, Tuple, Type

from .errors import (
    RetryExhausted,
    RateLimitError,
    ServerError,
    TimeoutError,
)

DEFAULT_RETRYABLE = (RateLimitError, ServerError, TimeoutError)


def jitter(base: float, spread: float = 0.2) -> float:
    return base * (1 + random.uniform(-spread, spread))


def _real_sleep(d: float) -> None:
    import time

    time.sleep(d)


class RetryPolicy:
    def __init__(
        self,
        attempts: int = 3,
        base_delay: float = 0.2,
        max_delay: float = 5.0,
        backoff: float = 2.0,
        retry_on: Tuple[Type[BaseException], ...] = DEFAULT_RETRYABLE,
        sleep: Optional[Callable[[float], None]] = None,
    ):
        self.attempts = attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff = backoff
        self.retry_on = retry_on
        self._sleep = sleep or _real_sleep

    def should_retry(self, exc: BaseException, attempt: int) -> bool:
        if attempt >= self.attempts:
            return False
        return isinstance(exc, self.retry_on)

    def delay_for(self, attempt: int) -> float:
        d = self.base_delay * (self.backoff ** (attempt - 1))
        d = min(d, self.max_delay)
        return jitter(d)

    def run(self, fn: Callable[[], object]) -> object:
        last: Optional[BaseException] = None
        for attempt in range(1, self.attempts + 1):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 - we re-raise intentionally
                last = e
                if not isinstance(e, self.retry_on):
                    raise  # non-retryable: propagate the original error
                if attempt >= self.attempts:
                    raise RetryExhausted(
                        f"exhausted after {self.attempts} attempts", cause=e, attempts=self.attempts
                    )
                self._sleep(self.delay_for(attempt))
        raise RetryExhausted(
            f"exhausted after {self.attempts} attempts", cause=last, attempts=self.attempts
        )
