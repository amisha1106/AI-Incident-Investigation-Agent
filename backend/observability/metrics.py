"""
Redis-backed observability metrics for IncidentIQ.
"""

import time

from infrastructure.redis_client import get_redis


METRICS_KEY = "incidentiq:observability:metrics"


def _increment(field: str, amount: int = 1):
    redis_client = get_redis()

    redis_client.hincrby(
        METRICS_KEY,
        field,
        amount,
    )


def record_investigation_started():
    _increment("investigations_started")


def record_investigation_completed(
    stop_reason: str,
    duration_seconds: float | None = None,
):
    _increment("investigations_completed")

    _increment(
        f"stop_reason:{stop_reason}"
    )

    if duration_seconds is not None:
        _record_duration(duration_seconds)


def record_investigation_failed(
    duration_seconds: float | None = None,
):
    _increment("investigations_failed")

    if duration_seconds is not None:
        _record_duration(duration_seconds)


def record_tool_usage(
    tool: str,
):
    _increment(
        f"tool_usage:{tool}"
    )


def _record_duration(
    duration_seconds: float,
):
    redis_client = get_redis()

    duration_ms = int(
        max(duration_seconds, 0.0) * 1000
    )

    redis_client.hincrby(
        METRICS_KEY,
        "total_duration_ms",
        duration_ms,
    )

    redis_client.hset(
        METRICS_KEY,
        "last_duration_ms",
        duration_ms,
    )


def get_metrics():

    redis_client = get_redis()

    data = redis_client.hgetall(
        METRICS_KEY
    )

    tool_usage = {}
    stop_reasons = {}

    for key, value in data.items():

        if key.startswith("tool_usage:"):

            tool_name = key[
                len("tool_usage:"):
            ]

            tool_usage[tool_name] = int(value)

        elif key.startswith("stop_reason:"):

            reason = key[
                len("stop_reason:"):
            ]

            stop_reasons[reason] = int(value)

    completed = int(
        data.get(
            "investigations_completed",
            0,
        )
    )

    failed = int(
        data.get(
            "investigations_failed",
            0,
        )
    )

    total_duration_ms = int(
        data.get(
            "total_duration_ms",
            0,
        )
    )

    last_duration_ms = int(
        data.get(
            "last_duration_ms",
            0,
        )
    )

    measured_runs = completed + failed

    average_duration_seconds = (
        total_duration_ms / measured_runs / 1000
        if measured_runs
        else 0.0
    )

    return {
        "investigations_started":
            int(
                data.get(
                    "investigations_started",
                    0,
                )
            ),

        "investigations_completed":
            completed,

        "investigations_failed":
            failed,

        "tool_usage":
            tool_usage,

        "stop_reasons":
            stop_reasons,

        "average_duration_seconds":
            round(
                average_duration_seconds,
                3,
            ),

        "last_duration_seconds":
            round(
                last_duration_ms / 1000,
                3,
            ),
    }