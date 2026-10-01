"""
Demo data seeding API routes.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from config import DATA_DIR
from rag.vectorstore import ingest_historical_incidents
from utils.data_generator import seed_data

router = APIRouter(
    prefix="/api/v1/seed",
    tags=["Seed"],
)

@router.post("")
def seed_demo_data():
    """
    Generate demo incident data and optionally ingest historical incidents.
    """

    try:
        result = seed_data(DATA_DIR)

        try:
            ingest_historical_incidents()
            rag_status = "Historical incidents ingested successfully."

        except Exception as e:
            logger.error(
                f"Historical incident ingestion failed: {e}"
            )
            rag_status = (
                "Demo data seeded, but historical incident "
                "ingestion is unavailable."
            )

        return {
            "success": True,
            "message": "Demo data seeded successfully.",
            "result": result,
            "rag_status": rag_status,
        }

    except Exception as e:
        logger.error(f"Failed to seed demo data: {e}")

        raise HTTPException(
            status_code=500,
            detail="Failed to seed demo data.",
        )