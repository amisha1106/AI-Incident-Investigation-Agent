"""
Background investigation worker.

Consumes investigation jobs from Redis
and executes the existing investigation pipeline.
"""

import signal
import time

from loguru import logger

from config import (
    WORKER_POLL_INTERVAL,
    WORKER_HEARTBEAT_INTERVAL,
    WORKER_HEARTBEAT_TTL,
)

from infrastructure.job_store import (
    claim_job,
    get_job,
    update_job,
    recover_stuck_jobs,
)

from infrastructure.cache import (
    get_cached,
    set_cached,
)

from infrastructure.redis_client import get_redis


running = True

WORKER_HEARTBEAT_KEY = "incidentiq:worker:heartbeat"


def update_worker_heartbeat():
    redis_client = get_redis()

    redis_client.set(
        WORKER_HEARTBEAT_KEY,
        time.time(),
        ex=WORKER_HEARTBEAT_TTL,
    )


def shutdown_handler(
    signum,
    frame,
):
    global running

    logger.info(
        "[Worker] Shutdown signal received."
    )

    running = False


signal.signal(
    signal.SIGTERM,
    shutdown_handler,
)

signal.signal(
    signal.SIGINT,
    shutdown_handler,
)


def process_job(
    job_id: str,
):

    from graph.workflow import run_investigation

    job = get_job(job_id)

    if job is None:
        logger.warning(
            f"[Worker] Job {job_id} no longer exists."
        )
        return

    query = job["query"]

    update_job(
        job_id,
        status="running",
        started_at=time.time(),
    )

    logger.info(
        f"[Worker] Starting job {job_id}"
    )

    try:

        # -------------------------------------------------
        # Cache lookup
        # -------------------------------------------------

        cached_result = get_cached(
            "investigation",
            query,
        )

        if cached_result is not None:

            logger.info(
                f"[Worker] Cache hit for job {job_id}"
            )

            update_job(
                job_id,
                status="completed",
                completed_at=time.time(),
                result=cached_result,
            )

            return

        logger.info(
            f"[Worker] Cache miss for job {job_id}"
        )

        # -------------------------------------------------
        # Run investigation
        # -------------------------------------------------

        state = run_investigation(
            query
        )

        # -------------------------------------------------
        # Store investigation result in cache
        # -------------------------------------------------

        set_cached(
            "investigation",
            query,
            state,
        )

        logger.info(
            f"[Worker] Investigation result cached for "
            f"job {job_id}"
        )

        # -------------------------------------------------
        # Complete job
        # -------------------------------------------------

        update_job(
            job_id,
            status="completed",
            completed_at=time.time(),
            result=state,
        )

        logger.info(
            f"[Worker] Completed job {job_id}"
        )

    except Exception as exc:

        logger.exception(
            f"[Worker] Job {job_id} failed: {exc}"
        )

        update_job(
            job_id,
            status="failed",
            completed_at=time.time(),
            error="Investigation failed.",
        )


def main():

    logger.info(
        "[Worker] IncidentIQ worker started."
    )

    last_recovery_check = 0.0

    while running:

        current_time = time.time()

        # -------------------------------------------------
        # Worker heartbeat
        # -------------------------------------------------

        update_worker_heartbeat()

        # -------------------------------------------------
        # Recover stuck jobs
        # -------------------------------------------------

        if (
            current_time - last_recovery_check
            >= WORKER_HEARTBEAT_INTERVAL
        ):

            recovered_jobs = recover_stuck_jobs()

            for recovered_job_id in recovered_jobs:
                logger.warning(
                    "[Worker] Recovered stuck job "
                    f"{recovered_job_id}"
                )

            last_recovery_check = current_time

        # -------------------------------------------------
        # Claim next job
        # -------------------------------------------------

        job_id = claim_job(
            timeout=5
        )

        if not job_id:

            time.sleep(
                WORKER_POLL_INTERVAL
            )

            continue

        try:

            process_job(
                job_id
            )

        except Exception as exc:

            logger.exception(
                f"[Worker] Unexpected job error: {exc}"
            )

    logger.info(
        "[Worker] Worker stopped."
    )


if __name__ == "__main__":
    main()