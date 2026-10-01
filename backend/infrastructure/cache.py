"""
Simple Redis-backed TTL cache.
"""

import json
import hashlib

from infrastructure.redis_client import get_redis
from config import CACHE_TTL_SECONDS


CACHE_PREFIX = "incidentiq:cache:"


def make_cache_key(
    namespace: str,
    value: str,
) -> str:

    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()

    return f"{CACHE_PREFIX}{namespace}:{digest}"


def get_cached(
    namespace: str,
    value: str,
):

    key = make_cache_key(
        namespace,
        value,
    )

    raw = get_redis().get(key)

    if raw is None:
        return None

    return json.loads(raw)


def set_cached(
    namespace: str,
    value: str,
    result,
    ttl: int = CACHE_TTL_SECONDS,
):

    key = make_cache_key(
        namespace,
        value,
    )

    get_redis().set(
        key,
        json.dumps(result, default=str),
        ex=ttl,
    )