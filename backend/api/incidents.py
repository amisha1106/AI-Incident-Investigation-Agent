"""
Incident investigation API routes.
"""

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from config import INVESTIGATION_TIMEOUT
from graph.workflow import run_investigation
from api.auth import verify_api_key
from api.models import InvestigationRequest, InvestigationResponse
from api.rate_limit import check_rate_limit
import uuid

from infrastructure.job_store import (
    create_job,
    get_job,
)
from api.models import (
    InvestigationJobResponse,
    InvestigationJobStatusResponse,
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
    check_rate_limit(http_request.client.host)

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    investigation_start = time.perf_counter()

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                run_investigation,
                request.query,
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
                raise HTTPException(
                    status_code=504,
                    detail="Investigation timed out.",
                )

        investigation_duration = (
            time.perf_counter() - investigation_start
        )

        return {
            "success": True,
            "query": request.query,
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

    check_rate_limit(
        http_request.client.host
    )

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    job_id = str(
        uuid.uuid4()
    )

    create_job(
        job_id=job_id,
        query=request.query,
    )

    audit_event(
        "investigation.created",
        job_id=job_id,
        request_id=getattr(
            http_request.state,
            "request_id",
            None,
        ),
        status="queued",
    )

    return {
        "job_id": job_id,
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

    check_rate_limit(
        http_request.client.host
    )

    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation job not found.",
        )

    return job