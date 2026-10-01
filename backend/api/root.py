"""
Root API routes.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/api",
    tags=["Root"],
)


@router.get("/v1")
def api_root():
    return {
        "name": "IncidentIQ API",
        "version": "1.0.0",
        "status": "running",
    }