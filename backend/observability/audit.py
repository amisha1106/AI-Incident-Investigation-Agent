"""
Audit event logging.
"""

import time
import uuid

from loguru import logger


def audit_event(
    event: str,
    *,
    job_id: str | None = None,
    request_id: str | None = None,
    status: str | None = None,
    tool: str | None = None,
    duration_seconds: float | None = None,
):

    event_id = str(
        uuid.uuid4()
    )

    logger.info(
        "AUDIT "
        f"event_id={event_id} "
        f"event={event} "
        f"job_id={job_id} "
        f"request_id={request_id} "
        f"status={status} "
        f"tool={tool} "
        f"duration={duration_seconds} "
        f"timestamp={time.time()}"
    )