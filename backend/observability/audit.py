"""
Audit logging for IncidentIQ investigations.
"""

import json
import time

from infrastructure.redis_client import get_redis


AUDIT_STREAM_KEY = "incidentiq:audit"


def audit_event(event: str, **details):
    """
    Persist a structured investigation audit event in Redis.
    """

    payload = {
        "timestamp": time.time(),
        "event": event,
        **details,
    }

    redis_client = get_redis()

    redis_client.rpush(
        AUDIT_STREAM_KEY,
        json.dumps(payload),
    )

    # Keep the audit stream bounded.
    redis_client.ltrim(
        AUDIT_STREAM_KEY,
        -5000,
        -1,
    )


def get_audit_events(limit: int = 100):
    """
    Return the most recent audit events.
    """

    redis_client = get_redis()

    raw_events = redis_client.lrange(
        AUDIT_STREAM_KEY,
        -limit,
        -1,
    )

    return [
        json.loads(event)
        for event in raw_events
    ]