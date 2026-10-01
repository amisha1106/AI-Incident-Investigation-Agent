"""
Health and readiness API routes.
"""

from fastapi import APIRouter

from infrastructure.redis_client import check_redis
from rag.vectorstore import get_vectorstore
import time

from infrastructure.redis_client import get_redis

WORKER_HEARTBEAT_KEY = "incidentiq:worker:heartbeat"
router = APIRouter(
    prefix="/api/v1/health",
    tags=["Health"],
)


@router.get("")
def health_check():
    """
    Liveness check.

    Confirms that the API process is running.
    """
    return {
        "status": "healthy",
    }


@router.get("/ready")
def readiness_check():
    """
    Readiness check.

    Confirms that the API can access its required
    Redis and RAG/vector-store dependencies.
    """

    try:

        if not check_redis():
            return {
                "status": "not_ready",
                "reason": "redis_unavailable",
            }

        get_vectorstore()

        return {
            "status": "ready",
        }

    except Exception:

        return {
            "status": "not_ready",
            "reason": "dependency_unavailable",
        }

@router.get("/worker")
def worker_health_check():
    """
    Check whether the background investigation worker
    has sent a recent heartbeat.
    """

    redis_client = get_redis()

    heartbeat = redis_client.get(
        WORKER_HEARTBEAT_KEY
    )

    if heartbeat is None:
        return {
            "status": "not_ready",
            "worker": "unknown",
        }

    heartbeat_age = (
        time.time() - float(heartbeat)
    )

    if heartbeat_age > 15:
        return {
            "status": "not_ready",
            "worker": "stale",
            "heartbeat_age_seconds": round(
                heartbeat_age,
                2,
            ),
        }

    return {
        "status": "healthy",
        "worker": "alive",
        "heartbeat_age_seconds": round(
            heartbeat_age,
            2,
        ),
    }
