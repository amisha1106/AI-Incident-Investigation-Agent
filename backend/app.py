"""
FastAPI backend for the Incident AI Agent.
Exposes REST endpoints consumed by the Streamlit frontend.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from api.observability import router as observability_router
from contextvars import ContextVar
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from config import (
    API_HOST,
    API_PORT,
    API_RELOAD,
    CORS_ALLOWED_ORIGINS,
)
from api.incidents import router as incidents_router
from api.data import router as data_router
from api.health import router as health_router
from api.root import router as root_router
from api.seed import router as seed_router

request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="",
)


app = FastAPI(
    title="IncidentIQ API",
    description=(
        "Evidence-driven incident investigation using a single "
        "Investigation Agent, specialized investigation tools, "
        "Gemini, and historical incident retrieval."
    ),
    version="1.0.0",
)

app.include_router(
    observability_router
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

import time
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.perf_counter()

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    request_id_context.set(request_id)

    response = await call_next(request)

    duration = time.perf_counter() - start_time

    response.headers["X-Request-ID"] = request_id

    logger.info(
        f"request_id={request_id} "
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} "
        f"({duration:.3f}s)"
    )

    return response

@app.exception_handler(Exception)
async def handle_unexpected_error(
    request: Request,
    exc: Exception,
):
    logger.exception(
        f"Unhandled API error: {request.method} {request.url.path}"
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error.",
        },
    )

app.include_router(incidents_router)
app.include_router(data_router)
app.include_router(health_router)
app.include_router(root_router)
app.include_router(seed_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
    app,
    host=API_HOST,
    port=API_PORT,
    reload=API_RELOAD,
)