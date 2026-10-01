from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from observability.metrics import get_metrics


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

    return get_metrics()