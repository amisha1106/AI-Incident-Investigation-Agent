"""
Retry, exponential backoff, jitter,
and circuit breaker utilities.
"""

import random
import time
from functools import wraps
from threading import Lock

from config import (
    GEMINI_MAX_RETRIES,
    GEMINI_RETRY_BASE_DELAY,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_RECOVERY_SECONDS,
)


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:

    def __init__(
        self,
        failure_threshold: int,
        recovery_seconds: int,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds

        self.failure_count = 0
        self.opened_at = None

        self._lock = Lock()

    def allow_request(self) -> bool:

        with self._lock:

            if self.opened_at is None:
                return True

            elapsed = (
                time.time() - self.opened_at
            )

            if elapsed >= self.recovery_seconds:
                return True

            return False

    def record_success(self):

        with self._lock:
            self.failure_count = 0
            self.opened_at = None

    def record_failure(self):

        with self._lock:

            self.failure_count += 1

            if (
                self.failure_count
                >= self.failure_threshold
            ):
                self.opened_at = time.time()

    def state(self) -> str:

        if self.opened_at is None:
            return "closed"

        if (
            time.time() - self.opened_at
            >= self.recovery_seconds
        ):
            return "half_open"

        return "open"


gemini_circuit = CircuitBreaker(
    failure_threshold=(
        CIRCUIT_BREAKER_FAILURE_THRESHOLD
    ),
    recovery_seconds=(
        CIRCUIT_BREAKER_RECOVERY_SECONDS
    ),
)


def retry_with_backoff(
    max_retries: int = GEMINI_MAX_RETRIES,
    base_delay: float = GEMINI_RETRY_BASE_DELAY,
):

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            last_error = None

            for attempt in range(
                max_retries + 1
            ):

                try:
                    return func(
                        *args,
                        **kwargs,
                    )

                except Exception as exc:

                    last_error = exc

                    if attempt >= max_retries:
                        raise

                    delay = (
                        base_delay
                        * (2 ** attempt)
                    )

                    jitter = random.uniform(
                        0,
                        delay * 0.25,
                    )

                    time.sleep(
                        delay + jitter
                    )

            raise last_error

        return wrapper

    return decorator