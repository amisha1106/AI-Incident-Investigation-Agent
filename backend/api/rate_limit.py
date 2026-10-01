"""
Simple in-memory API rate limiter.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, status

from config import API_RATE_LIMIT


WINDOW_SECONDS = 60

_request_counts: dict[str, tuple[int, float]] = defaultdict(
    lambda: (0, 0.0)
)


def check_rate_limit(client_key: str) -> None:
    """
    Allow up to API_RATE_LIMIT requests per minute per client key.
    """

    now = time.monotonic()

    count, window_start = _request_counts[client_key]

    if now - window_start >= WINDOW_SECONDS:
        _request_counts[client_key] = (1, now)
        return

    if count >= API_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )

    _request_counts[client_key] = (
        count + 1,
        window_start,
    )