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

# ── RAG ────────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"      # free, runs locally
RAG_TOP_K = 3
RAG_COLLECTION_NAME = "historical_incidents"

# ── Agent ──────────────────────────────────────────────────────────────────
MAX_AGENT_ITERATIONS = 10
CONFIDENCE_THRESHOLD = 0.7

# ── Evaluation ─────────────────────────────────────────────────────────────
RUN_EVALUATION = os.getenv("RUN_EVALUATION", "false").lower() == "true"
