"""
FastAPI backend for the Incident AI Agent.
Exposes REST endpoints consumed by the Streamlit frontend.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
from datetime import datetime

from graph.workflow import run_investigation
from rag.vectorstore import ingest_historical_incidents
from utils.data_generator import seed_data
from utils.parser import load_logs, load_metrics, load_deployments, summarize_logs, summarize_metrics, summarize_deployments
from config import DATA_DIR

app = FastAPI(
    title="Incident AI Agent API",
    description="Multi-agent incident investigation using LangGraph + Gemini + ChromaDB",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ─────────────────────────────────────────────────
class InvestigationRequest(BaseModel):
    query: str


class SeedRequest(BaseModel):
    incident_time: str | None = None  # ISO format, optional


# ── Routes ──────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/seed")
def seed_demo_data(request: SeedRequest = SeedRequest()):
    """Seed synthetic incident data and ingest into vector store."""
    try:
        incident_time = None
        if request.incident_time:
            incident_time = datetime.fromisoformat(request.incident_time)

        result = seed_data(DATA_DIR, incident_time)
        count = ingest_historical_incidents(force=True)
        result["vectorstore_count"] = count
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Seed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/investigate")
def investigate(request: InvestigationRequest):
    """
    Run the full multi-agent incident investigation workflow.
    Returns: complete state with RCA, report, and agent findings.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        state = run_investigation(request.query)
        return {
            "success": True,
            "query": request.query,
            "plan": state.get("plan", {}),
            "log_findings": state.get("log_findings", {}),
            "metrics_findings": state.get("metrics_findings", {}),
            "deployment_findings": state.get("deployment_findings", {}),
            "rca": state.get("rca", {}),
            "similar_incidents": state.get("similar_incidents", []),
            "final_report": state.get("final_report", ""),
            "messages": state.get("messages", []),
        }
    except Exception as e:
        logger.error(f"Investigation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/overview")
def data_overview():
    """Return a summary of the current data state."""
    logs = load_logs()
    metrics = load_metrics()
    deployments = load_deployments()

    return {
        "logs": summarize_logs(logs) if logs else {"count": 0},
        "metrics": summarize_metrics(metrics) if metrics else {"count": 0},
        "deployments": summarize_deployments(deployments) if deployments else {"count": 0},
    }


@app.get("/data/metrics")
def get_metrics():
    """Return raw metrics for charting in the UI."""
    return load_metrics()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
