"""
Data-related API routes.
"""

from fastapi import APIRouter
from api.models import MetricsResponse
from utils.parser import (
    load_logs,
    load_metrics,
    load_deployments,
    summarize_logs,
    summarize_metrics,
    summarize_deployments,
)

router = APIRouter(
    prefix="/api/v1/data",
    tags=["Data"],
)


@router.get("/overview")
def data_overview():
    """
    Return a summary of available incident data.
    """

    logs = load_logs()
    metrics = load_metrics()
    deployments = load_deployments()

    return {
        "logs": summarize_logs(logs),
        "metrics": summarize_metrics(metrics),
        "deployments": summarize_deployments(deployments),
    }


@router.get(
    "/metrics",
    response_model=MetricsResponse,
)
def get_metrics():
    """
    Return parsed metrics data.
    """

    metrics = load_metrics()

    return {
        "metrics": metrics,
    }