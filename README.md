# 🔍 AI Incident Investigation Agent

> **Production-grade multi-agent system for automated Root Cause Analysis using LangGraph, Gemini, ChromaDB, and DeepEval.**


[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Gemini](https://img.shields.io/badge/Gemini-3.5--Flash-orange.svg)](https://aistudio.google.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 What This Does

When a production incident occurs, this agent autonomously:

1. **Plans** the investigation based on your natural language description
2. **Analyzes logs** for error patterns and anomalies
3. **Detects metric anomalies** (latency spikes, error rate increases, DB saturation)
4. **Correlates deployments** with the incident timeline
5. **Searches historical incidents** using semantic RAG (ChromaDB + sentence-transformers)
6. **Synthesizes a root cause** with confidence scoring and evidence
7. **Generates a full RCA report** with immediate actions and long-term prevention

**Example:**

```
Input: "Checkout latency increased 10x after deployment v3.8. Error rate jumped to 8%."

Output:
  Root Cause (87% confidence): Deployment v3.8 introduced a database connection
  leak in the payment retry logic. The retry loop fails to close connections,
  causing pool saturation at 94%. This matches historical incident INC-2025-001.

  Immediate Actions:
  1. Roll back deployment v3.8
  2. Fix connection.close() in retry loop
  3. Increase pool size as temporary stopgap
```

---

## 🏗️ Architecture

```
                        User Query
                             │
                    ┌────────▼────────┐
                    │  Planner Agent  │
                    │ (Investigation  │
                    │     Plan)       │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐  ┌───────▼───────┐  ┌─────▼──────────┐
    │  Log Agent  │  │ Metrics Agent │  │Deployment Agent │
    │(Error       │  │(Latency,      │  │(Version        │
    │ Patterns)   │  │ Error Rate,   │  │ Correlation)   │
    └──────┬──────┘  │ DB Saturation)│  └─────┬──────────┘
           │         └───────┬───────┘        │
           └─────────────────┼────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Historical RAG │
                    │  (ChromaDB +    │
                    │  MiniLM-L6-v2)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Root Cause Agent│
                    │  (Synthesis +   │
                    │  Confidence)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  DeepEval       │
                    │  Validation     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Final RCA      │
                    │  Report (MD)    │
                    └─────────────────┘
```

---

## 🛠️ Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM | Gemini 1.5 Flash | Free tier, 1M TPD, excellent reasoning |
| Multi-agent orchestration | LangGraph | Production-grade stateful graphs |
| Vector database | ChromaDB (local) | Zero cost, no server needed |
| Embeddings | all-MiniLM-L6-v2 | Free, runs locally via sentence-transformers |
| Backend | FastAPI | High-performance REST API |
| Frontend | Streamlit | Rapid prototyping with charts |
| Evaluation | DeepEval + RAGAS | LLM output quality measurement |
| Containerization | Docker | Reproducible deployments |

**Total API cost: $0** (Gemini free tier: 15 RPM, 1M tokens/day)

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/incident-ai-agent.git
cd incident-ai-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Get Free Gemini API Key

Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — it's free, no credit card needed.

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Run (Standalone Mode — no backend needed)

```bash
streamlit run frontend/streamlit_app.py
```

Open http://localhost:8501, add your API key, seed demo data, and investigate!

### 4. Run with FastAPI Backend (Optional)

```bash
# Terminal 1: Backend
cd backend
uvicorn app:app --port 8000 --reload

# Terminal 2: Frontend
streamlit run frontend/streamlit_app.py
```

### 5. Docker (Optional)

```bash
GEMINI_API_KEY=your_key_here docker-compose up
```

---

## 📁 Project Structure

```
incident-ai-agent/
│
├── frontend/
│   └── streamlit_app.py         # Streamlit UI with charts
│
├── backend/
│   ├── app.py                   # FastAPI REST API
│   ├── config.py                # Central configuration
│   ├── requirements.txt
│   │
│   ├── agents/
│   │   ├── planner.py           # Investigation plan agent
│   │   ├── log_agent.py         # Log analysis agent
│   │   ├── metrics_agent.py     # Metrics anomaly agent
│   │   ├── deployment_agent.py  # Deployment correlation agent
│   │   ├── rootcause_agent.py   # RCA synthesis + RAG agent
│   │   └── summarizer.py        # Report generation agent
│   │
│   ├── graph/
│   │   └── workflow.py          # LangGraph StateGraph definition
│   │
│   ├── rag/
│   │   └── vectorstore.py       # ChromaDB ingest + retrieval
│   │
│   ├── llm/
│   │   └── gemini.py            # Gemini API wrapper
│   │
│   ├── data/
│   │   ├── logs/                # Application log JSON
│   │   ├── metrics/             # Time-series metric JSON
│   │   ├── deployments/         # Deployment history JSON
│   │   └── incidents/           # Historical incidents (RAG source)
│   │
│   ├── evaluation/
│   │   ├── deepeval_test.py     # DeepEval test suite
│   │   └── ragas_eval.py        # RAGAS RAG evaluation
│   │
│   ├── prompts/
│   │   ├── planner.txt          # Planner system prompt
│   │   └── rootcause.txt        # RCA system prompt
│   │
│   └── utils/
│       ├── data_generator.py    # Synthetic data generator
│       └── parser.py            # Data loading & summarization
│
├── .github/workflows/ci.yml     # GitHub Actions CI
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 🧪 Evaluation

### DeepEval Tests

```bash
cd backend
python -m pytest evaluation/deepeval_test.py -v
```

Tests include:
- **Answer Relevancy**: Root cause is relevant to the query
- **Faithfulness**: Report is grounded in evidence (not hallucinated)
- **Hallucination**: Agent doesn't fabricate data
- **Root Cause Specificity**: Custom test for technical detail quality
- **Confidence Range**: Confidence scores are realistic (50-98%)

### RAGAS Evaluation

```bash
cd backend
python evaluation/ragas_eval.py
```

Measures RAG pipeline quality:
- Context Precision
- Context Recall
- Answer Relevancy
- Faithfulness

---

## 📊 Example Investigation Output

```markdown
# 🔍 Incident Investigation Report

## Summary
Incident: Checkout latency spiked after deployment v3.8
Priority: HIGH | Severity: HIGH | Service: checkout-service

## 🟢 Root Cause (87% Confidence)
Deployment v3.8 introduced a database connection leak in the payment retry
logic. The retry loop fails to close DB connections on failure, causing
connection pool saturation (94%). Once saturated, all new checkout requests
began timing out, driving latency from 200ms to 4500ms and error rate to 8.5%.

## 🧾 Evidence
✅ Error rate increased from 0.3% → 8.5% immediately after deployment v3.8
✅ DB connection pool hit 94% saturation at 10:07 (6 min after deploy)
✅ Latency P99 spiked: 200ms → 4500ms
✅ CPU and memory remained stable (not resource exhaustion)
✅ Similar pattern in historical incident INC-2025-001 (Feb 2025)

## 🚨 Immediate Actions
1. Roll back deployment v3.8 to v3.7 immediately
2. Fix connection.close() in the payment retry loop
3. Temporarily increase DB connection pool size (max=30 → 50)
4. Add Grafana alert: DB pool > 70%
```

---

## 🔧 Extending the Agent

### Add a new agent

1. Create `backend/agents/my_agent.py` with a `run_my_agent(state: dict) -> dict` function
2. Register it in `backend/graph/workflow.py`:
   ```python
   graph.add_node("my_agent", run_my_agent)
   graph.add_edge("deployment_agent", "my_agent")
   graph.add_edge("my_agent", "rootcause_agent")
   ```

### Add real data sources

Replace the JSON loaders in `utils/parser.py` with real Datadog/CloudWatch/Splunk API calls.

### Add MCP tools (Phase 2)

```python
# In agents, call real tools via MCP
from langchain_mcp_adapters.client import MultiServerMCPClient
```

---

## 📄 License

MIT © 2025

---

## 🙏 Acknowledgements

Built with [LangGraph](https://github.com/langchain-ai/langgraph), [Google Gemini](https://aistudio.google.com), [ChromaDB](https://www.trychroma.com/), [DeepEval](https://github.com/confident-ai/deepeval), and [RAGAS](https://github.com/explodinggradients/ragas).
