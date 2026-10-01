# 🔍 AI Incident Investigation Agent

> **Production-grade evidence-driven system for automated Root Cause Analysis using a single Investigation Agent, Gemini, ChromaDB, FastAPI, Redis, and DeepEval.**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-orchestration-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Gemini](https://img.shields.io/badge/Gemini-3.5--Flash-orange.svg)](https://aistudio.google.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 What This Does

When a production incident occurs, IncidentIQ dynamically investigates the incident instead of following a fixed investigation sequence.

1. **Understands the incident** from a natural language description
2. **Selects the next investigation tool** based on the evidence already collected
3. **Analyzes logs** for errors, patterns, and anomalies
4. **Investigates metrics** such as latency, error rates, and database signals
5. **Correlates deployments** with the incident timeline
6. **Inspects APIs, databases, infrastructure, and security signals** when relevant
7. **Searches historical incidents** using semantic RAG
8. **Synthesizes an evidence-supported root cause** with confidence and alternatives
9. **Generates recommended actions and prevention steps**
10. **Reports insufficient evidence** when the available data does not support a reliable conclusion

**Example:**

```text
Input:
"Payment API latency increased after a recent deployment
with intermittent timeout errors."

Investigation:

Incident
   ↓
Investigation Agent
   ↓
Select relevant evidence sources
   ↓
Deployments → Database → Logs → API
   ↓
Evidence + Hypotheses + Evidence Gaps
   ↓
Final Synthesis

Output:
Root Cause: Most likely contributing factor identified from collected evidence
Confidence: Medium
Evidence: Supporting observations from multiple investigation tools
Actions: Recommended remediation and prevention steps
```

---

## 🏗️ Architecture

```text
                         Incident
                            │
                            ▼
                 ┌────────────────────┐
                 │ Investigation Agent│
                 │    / Orchestrator  │
                 └─────────┬──────────┘
                           │
                 "What should I
                  investigate next?"
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
        Logs            Metrics          Deployments
          │                │                 │
          └────────────────┼─────────────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
            API            DB       Infrastructure
             │             │             │
             └─────────────┼─────────────┘
                           │
                    Historical RAG
                           │
                           ▼
                 ┌─────────────────┐
                 │ Final Synthesis │
                 └────────┬────────┘
                          │
                          ▼
                 Final RCA Report
              Evidence + Confidence
              Actions + Prevention
```

The core design is **one Investigation Agent + specialized investigation tools + final synthesis**.

The Investigation Agent decides what to investigate next based on the incident, collected evidence, hypotheses, and remaining evidence gaps. It does not require every tool to run for every incident.

---

## 🛠️ Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM | Gemini 3.5 Flash | Reasoning, tool selection, and final synthesis |
| Investigation | Single Investigation Agent | Dynamic evidence-driven investigation |
| Orchestration | LangGraph workflow | Stateful investigation execution |
| Investigation Tools | Python | Logs, metrics, deployments, API, DB, infrastructure, security, RAG |
| Vector Database | ChromaDB | Historical incident retrieval |
| Backend | FastAPI | REST API and service endpoints |
| Frontend | Streamlit | Investigation UI and diagnostics |
| Jobs / Cache | Redis | Async jobs, caching, and shared state |
| Worker | Python background worker | Asynchronous investigation execution |
| Evaluation | DeepEval + RAGAS | LLM and RAG quality measurement |
| Resilience | Circuit breaker + fallbacks | Graceful handling of LLM/service failures |
| Containerization | Docker + Docker Compose | Reproducible local deployment |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/amisha1106/AI-Incident-Investigation-Agent.git

cd AI-Incident-Investigation-Agent

# Create virtual environment
python -m venv venv

source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r backend/requirements.txt
```

### 2. Configure Gemini API Key

Get a Gemini API key from Google AI Studio.

```bash
cp .env.example .env

# Edit .env and add your GEMINI_API_KEY
```

Example:

```env
GEMINI_API_KEY=your_key_here
```

### 3. Run with Docker

```bash
docker compose up -d --build
```

The stack starts:

```text
Backend    → http://localhost:8000
Frontend   → http://localhost:8501
API Docs   → http://localhost:8000/docs
Redis      → internal service
Worker     → background investigation service
```

### 4. Run Locally

Backend:

```bash
cd backend
uvicorn app:app --port 8000 --reload
```

Frontend:

```bash
streamlit run frontend/streamlit_app.py
```

### 5. Health Checks

```text
GET /api/v1/health
GET /api/v1/health/ready
GET /api/v1/health/worker
```

---

## 📁 Project Structure

```text
AI-Incident-Investigation-Agent/
│
├── frontend/
│   └── streamlit_app.py         # Streamlit investigation UI
│
├── backend/
│   ├── app.py                   # FastAPI application
│   ├── config.py                # Central configuration
│   ├── requirements.txt
│   │
│   ├── agents/
│   │   ├── investigation_agent.py  # Dynamic investigation reasoning
│   │   ├── orchestrator.py          # Investigation execution loop
│   │   └── final_synthesis.py       # Final RCA synthesis
│   │
│   ├── tools/
│   │   └── investigation_tools.py   # Investigation evidence tools
│   │
│   ├── graph/
│   │   └── workflow.py              # Investigation workflow
│   │
│   ├── api/
│   │   ├── incidents.py              # Investigation endpoints
│   │   ├── health.py                 # Health/readiness checks
│   │   ├── data.py                   # Data endpoints
│   │   ├── auth.py                   # API authentication
│   │   └── observability.py          # Metrics endpoint
│   │
│   ├── infrastructure/
│   │   ├── job_store.py              # Redis-backed job state
│   │   ├── cache.py                  # Investigation cache
│   │   ├── redis_client.py            # Redis connection
│   │   └── resilience.py             # Retry/circuit-breaker utilities
│   │
│   ├── workers/
│   │   └── investigation_worker.py   # Background job worker
│   │
│   ├── rag/
│   │   └── vectorstore.py             # Historical incident retrieval
│   │
│   ├── llm/
│   │   └── gemini.py                  # Gemini API integration
│   │
│   ├── observability/
│   │   ├── metrics.py                 # Investigation metrics
│   │   └── audit.py                   # Audit events
│   │
│   ├── evaluation/
│   │   ├── deepeval_test.py            # DeepEval tests
│   │   └── ragas_eval.py               # RAGAS evaluation
│   │
│   ├── prompts/
│   │   ├── planner.txt
│   │   └── rootcause.txt
│   │
│   └── utils/
│       ├── data_generator.py            # Synthetic data generator
│       └── parser.py                    # Data loading and parsing
│
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── README.md
```

---

## 🧪 Evaluation

### DeepEval Tests

```bash
cd backend

python -m pytest evaluation/deepeval_test.py -v
```

Tests cover areas such as:

- **Answer Relevancy**: Investigation result is relevant to the incident
- **Faithfulness**: Conclusions are grounded in collected evidence
- **Hallucination**: The system avoids fabricating telemetry
- **Root Cause Specificity**: RCA contains useful technical detail
- **Confidence Range**: Confidence is represented as a calibrated value

### RAGAS Evaluation

```bash
cd backend

python evaluation/ragas_eval.py
```

Measures RAG pipeline quality using:

- Context Precision
- Context Recall
- Answer Relevancy
- Faithfulness

---

## 📊 Example Investigation Output

The following is an illustrative example of the type of report IncidentIQ produces:

```markdown
# 🔍 Incident Investigation Report

## Summary

Incident:
Payment API latency increased after a recent deployment
with intermittent timeout errors.

## Root Cause

The available evidence indicates database connection
pressure as a likely contributor to the incident.

Confidence: Medium

## 🧾 Evidence

- Database connection usage increased during the incident
- Timeout-related errors appeared in application logs
- A recent deployment overlaps with the incident timeline
- API latency increased during the same period

## ⚠️ Evidence Gaps

- No distributed tracing data available
- No direct application code inspection
- Infrastructure telemetry may be incomplete

## 🚨 Recommended Actions

1. Inspect database connection pool configuration
2. Review the recent deployment changes
3. Check application connection lifecycle handling
4. Add alerts for database connection saturation
```

IncidentIQ does not treat confidence as proof of causality. When evidence is incomplete or conflicting, the final result can explicitly report insufficient evidence.

---

## 🔧 Extending the Agent

### Add a new investigation tool

Create a new tool in:

```text
backend/tools/investigation_tools.py
```

Examples of investigation capabilities include:

```text
query_logs()
query_metrics()
get_deployments()
inspect_api()
inspect_database()
inspect_infrastructure()
inspect_security()
search_historical_incidents()
```

Register the new capability with the Investigation Agent so it can be selected when relevant.

The important design principle is that **tools collect evidence while the Investigation Agent performs the investigation reasoning**.

### Add real data sources

The current tools work with the project's available telemetry.

They can be extended to connect with real production platforms such as:

```text
Logs:
- Loki
- Splunk
- Elasticsearch
- Datadog

Metrics:
- Prometheus
- Grafana
- Datadog

Deployments:
- GitHub
- GitLab
- Jenkins
- ArgoCD

Infrastructure:
- Kubernetes
- AWS
- Azure
- GCP
```

This allows the same investigation architecture to evolve from local/demo telemetry toward real observability environments.

---

## 📄 License

MIT © 2026

---

## 🙏 Acknowledgements

Built with [LangGraph](https://github.com/langchain-ai/langgraph), [Google Gemini](https://ai.google.dev/), [ChromaDB](https://www.trychroma.com/), [FastAPI](https://fastapi.tiangolo.com/), [Streamlit](https://streamlit.io/), [DeepEval](https://github.com/confident-ai/deepeval), and [RAGAS](https://github.com/explodinggradients/ragas).
'''