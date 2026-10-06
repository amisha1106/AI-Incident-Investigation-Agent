"""
IncidentIQ Investigation API routes.
"""

import time
import uuid

from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from loguru import logger

from config import INVESTIGATION_TIMEOUT

from graph.workflow import run_investigation

from api.auth import verify_api_key

from api.models import (
    InvestigationRequest,
    InvestigationResponse,
    InvestigationJobResponse,
    InvestigationJobStatusResponse,
)

from api.rate_limit import check_rate_limit

from infrastructure.job_store import (
    create_job,
    get_job,
)

from observability.audit import audit_event


router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Incidents"],
)


@router.post(
    "/investigate",
    response_model=InvestigationResponse,
)
def investigate_incident(
    request: InvestigationRequest,
    http_request: Request,
    _: None = Depends(verify_api_key),
):
    """
    Run a synchronous incident investigation.
    """

    check_rate_limit(
        http_request.client.host
    )

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    request_id = getattr(
        http_request.state,
        "request_id",
        None,
    )

    investigation_start = time.perf_counter()

    audit_event(
        "investigation.created",
        request_id=request_id,
        job_id=None,
        status="started",
        mode="sync",
    )

    try:

        with ThreadPoolExecutor(
            max_workers=1
        ) as executor:

            future = executor.submit(
                run_investigation,
                request.query,
                None,
                request_id,
                None,
            )

            try:

                state = future.result(
                    timeout=INVESTIGATION_TIMEOUT
                )

            except TimeoutError:

                logger.error(
                    f"Investigation timed out after "
                    f"{INVESTIGATION_TIMEOUT} seconds."
                )

                audit_event(
                    "investigation.timeout",
                    request_id=request_id,
                    job_id=None,
                    investigation_id=state.get(
                        "investigation_id"
                    )
                    if "state" in locals()
                    else None,
                )

                raise HTTPException(
                    status_code=504,
                    detail="Investigation timed out.",
                )

        investigation_duration = (
            time.perf_counter()
            - investigation_start
        )

        return {
            "success": True,
            "query": request.query,

            "request_id": state.get(
                "request_id",
                request_id,
            ),

            "job_id": state.get(
                "job_id"
            ),

            "investigation_id": state.get(
                "investigation_id"
            ),

            "observations": state.get(
                "observations",
                [],
            ),

            "evidence": state.get(
                "evidence",
                [],
            ),

            "hypotheses": state.get(
                "hypotheses",
                [],
            ),

            "tools_used": state.get(
                "tools_used",
                [],
            ),

            "evidence_gaps": state.get(
                "evidence_gaps",
                [],
            ),

            "confidence": state.get(
                "confidence",
                0.0,
            ),

            "investigation_duration_seconds": round(
                investigation_duration,
                3,
            ),

            "stop_reason": state.get(
                "stop_reason",
                "max_iterations_reached",
            ),

            "final_result": state.get(
                "final_result",
                {},
            ),
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.error(
            f"Investigation failed: {e}"
        )

        audit_event(
            "investigation.api_failed",
            request_id=request_id,
            job_id=None,
            error=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail="Investigation failed.",
        )


@router.post(
    "/investigate/async",
    response_model=InvestigationJobResponse,
    status_code=202,
)
def investigate_incident_async(
    request: InvestigationRequest,
    http_request: Request,
    _: None = Depends(verify_api_key),
):
    """
    Queue an asynchronous investigation job.
    """

    check_rate_limit(
        http_request.client.host
    )

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    request_id = getattr(
        http_request.state,
        "request_id",
        None,
    )

    job_id = str(
        uuid.uuid4()
    )

    create_job(
        job_id=job_id,
        query=request.query,
        request_id=request_id,
    )

    audit_event(
        "investigation.created",
        request_id=request_id,
        job_id=job_id,
        investigation_id=None,
        status="queued",
        mode="async",
    )

    return {
        "job_id": job_id,
        "request_id": request_id,
        "status": "queued",
    }


@router.get(
    "/jobs/{job_id}",
    response_model=InvestigationJobStatusResponse,
)
def get_investigation_job(
    job_id: str,
    http_request: Request,
    _: None = Depends(verify_api_key),
):
    """
    Retrieve the status/result of an asynchronous investigation.
    """

    check_rate_limit(
        http_request.client.host
    )

    job = get_job(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation job not found.",
        )

    return job