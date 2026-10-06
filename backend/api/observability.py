from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from api.auth import verify_api_key

from observability.metrics import get_metrics

from observability.audit import get_audit_events


router = APIRouter(
    prefix="/api/v1/observability",
    tags=["Observability"],
)


@router.get(
    "/metrics",
)
def metrics(
    _: None = Depends(verify_api_key),
):
    """
    Return current IncidentIQ metrics.
    """

    return get_metrics()


@router.get(
    "/audit",
)
def audit(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),

    investigation_id: str | None = Query(
        default=None,
    ),

    request_id: str | None = Query(
        default=None,
    ),

    job_id: str | None = Query(
        default=None,
    ),

    _: None = Depends(verify_api_key),
):
    """
    Return audit events with optional correlation filters.
    """

    events = get_audit_events(
        limit
    )

    if investigation_id:

        events = [
            event
            for event in events
            if event.get(
                "investigation_id"
            ) == investigation_id
        ]

    if request_id:

        events = [
            event
            for event in events
            if event.get(
                "request_id"
            ) == request_id
        ]

    if job_id:

        events = [
            event
            for event in events
            if event.get(
                "job_id"
            ) == job_id
        ]

    return {
        "events": events,
    }