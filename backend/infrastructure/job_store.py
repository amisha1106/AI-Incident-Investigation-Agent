"""
Redis-backed investigation job state.
"""

import json
import time

from infrastructure.redis_client import get_redis
from config import (
    JOB_TTL_SECONDS,
    WORKER_JOB_TIMEOUT,
)


JOB_PREFIX = "incidentiq:job:"
QUEUE_KEY = "incidentiq:investigation:queue"
RUNNING_SET_KEY = "incidentiq:investigation:running"


def _job_key(job_id: str) -> str:
    return f"{JOB_PREFIX}{job_id}"


def create_job(
    job_id: str,
    query: str,
) -> dict:

    job = {
        "job_id": job_id,
        "status": "queued",
        "query": query,
        "created_at": time.time(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }

    redis = get_redis()

    redis.set(
        _job_key(job_id),
        json.dumps(job),
        ex=JOB_TTL_SECONDS,
    )

    redis.rpush(
        QUEUE_KEY,
        job_id,
    )

    return job


def get_job(
    job_id: str,
) -> dict | None:

    raw = get_redis().get(
        _job_key(job_id)
    )

    if not raw:
        return None

    return json.loads(raw)


def update_job(
    job_id: str,
    **updates,
) -> dict | None:

    job = get_job(job_id)

    if job is None:
        return None

    job.update(updates)

    redis = get_redis()

    redis.set(
        _job_key(job_id),
        json.dumps(job),
        ex=JOB_TTL_SECONDS,
    )

    status = job.get("status")

    if status == "running":
        redis.sadd(
            RUNNING_SET_KEY,
            job_id,
        )

    elif status in {
        "completed",
        "failed",
    }:
        redis.srem(
            RUNNING_SET_KEY,
            job_id,
        )

    return job


def claim_job(
    timeout: int = 5,
) -> str | None:

    result = get_redis().blpop(
        QUEUE_KEY,
        timeout=timeout,
    )

    if not result:
        return None

    _, job_id = result

    return job_id


def recover_stuck_jobs() -> list[str]:
    """
    Recover jobs that have remained in the running state
    longer than WORKER_JOB_TIMEOUT.
    """

    redis = get_redis()

    running_job_ids = redis.smembers(
        RUNNING_SET_KEY
    )

    recovered_jobs = []

    now = time.time()

    for job_id in running_job_ids:

        job = get_job(job_id)

        if job is None:
            redis.srem(
                RUNNING_SET_KEY,
                job_id,
            )
            continue

        if job.get("status") != "running":
            redis.srem(
                RUNNING_SET_KEY,
                job_id,
            )
            continue

        started_at = job.get("started_at")

        if started_at is None:
            continue

        elapsed = now - float(started_at)

        if elapsed <= WORKER_JOB_TIMEOUT:
            continue

        update_job(
            job_id,
            status="failed",
            completed_at=now,
            error="Investigation worker timed out.",
        )

        recovered_jobs.append(job_id)

    return recovered_jobs