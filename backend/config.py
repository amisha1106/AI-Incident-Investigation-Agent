"""
Central configuration for the Incident AI Agent system.
All settings loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
METRICS_DIR = DATA_DIR / "metrics"
DEPLOYMENTS_DIR = DATA_DIR / "deployments"
INCIDENTS_DIR = DATA_DIR / "incidents"
PROMPTS_DIR = BASE_DIR / "prompts"
CHROMA_DB_PATH = BASE_DIR / os.getenv("CHROMA_DB_PATH", "chroma_db")

# ── Gemini ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash"          # free tier
GEMINI_TEMPERATURE = 0.2
GEMINI_MAX_TOKENS = 2048
GEMINI_REQUEST_TIMEOUT = int(
    os.getenv("GEMINI_REQUEST_TIMEOUT", "10")
)

# ── API ────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8501",
    ).split(",")
    if origin.strip()
]

API_KEY = os.getenv("API_KEY", "")
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "20"))
INVESTIGATION_TIMEOUT = int(
    os.getenv("INVESTIGATION_TIMEOUT", "60")
)

# ── RAG ────────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"      # free, runs locally
RAG_TOP_K = 3
RAG_COLLECTION_NAME = "historical_incidents"

# ── Agent ──────────────────────────────────────────────────────────────────
MAX_AGENT_ITERATIONS = 10
CONFIDENCE_THRESHOLD = 0.7

# ── Evaluation ─────────────────────────────────────────────────────────────
RUN_EVALUATION = os.getenv("RUN_EVALUATION", "false").lower() == "true"

# ── Redis ─────────────────────────────────────────────────────────────
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://redis:6379/0",
)

JOB_TTL_SECONDS = int(
    os.getenv("JOB_TTL_SECONDS", "3600")
)

CACHE_TTL_SECONDS = int(
    os.getenv("CACHE_TTL_SECONDS", "300")
)

WORKER_POLL_INTERVAL = float(
    os.getenv("WORKER_POLL_INTERVAL", "1.0")
)

WORKER_HEARTBEAT_INTERVAL = int(
    os.getenv("WORKER_HEARTBEAT_INTERVAL", "5")
)

WORKER_HEARTBEAT_TTL = int(
    os.getenv("WORKER_HEARTBEAT_TTL", "15")
)

WORKER_JOB_TIMEOUT = int(
    os.getenv("WORKER_JOB_TIMEOUT", "120")
)

GEMINI_MAX_RETRIES = int(
    os.getenv("GEMINI_MAX_RETRIES", "2")
)

GEMINI_RETRY_BASE_DELAY = float(
    os.getenv("GEMINI_RETRY_BASE_DELAY", "0.5")
)

CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(
    os.getenv(
        "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        "3",
    )
)

CIRCUIT_BREAKER_RECOVERY_SECONDS = int(
    os.getenv(
        "CIRCUIT_BREAKER_RECOVERY_SECONDS",
        "60",
    )
)