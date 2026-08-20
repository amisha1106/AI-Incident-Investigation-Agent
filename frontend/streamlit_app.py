"""
Streamlit UI for the Incident AI Investigation Agent.

Run: streamlit run frontend/streamlit_app.py
(Make sure backend is running: uvicorn backend.app:app --port 8000)

Or run standalone (no backend needed): set STANDALONE=true
"""

import sys
import os

# Allow running from repo root or frontend dir
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, ROOT)

import streamlit as st
import json
import time
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# Try to import backend directly (standalone mode)
try:
    from graph.workflow import run_investigation
    from utils.data_generator import seed_data
    from utils.parser import load_metrics, summarize_metrics
    from rag.vectorstore import ingest_historical_incidents
    from config import DATA_DIR
    STANDALONE = True
except ImportError:
    STANDALONE = False
    import httpx
    API_BASE = os.getenv("API_BASE", "http://localhost:8000")


# ── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Incident Investigator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .agent-card {
        background: #f8f9fa;
        border-left: 4px solid #0f3460;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .confidence-high { color: #28a745; font-weight: bold; font-size: 1.2em; }
    .confidence-medium { color: #ffc107; font-weight: bold; font-size: 1.2em; }
    .confidence-low { color: #dc3545; font-weight: bold; font-size: 1.2em; }
    .stProgress > div > div > div { background-color: #0f3460; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Incident AI Agent")
    st.markdown("*Multi-agent RCA powered by LangGraph + Gemini*")
    st.divider()

    st.markdown("#### ⚙️ Setup")
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        help="Get free key at https://aistudio.google.com/app/apikey",
        value=os.getenv("GEMINI_API_KEY", ""),
    )
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    st.divider()
    st.markdown("#### 📥 Demo Data")
    if st.button("🌱 Seed Demo Incident Data", use_container_width=True):
        with st.spinner("Seeding synthetic data..."):
            try:
                if STANDALONE:
                    result = seed_data(DATA_DIR)
                    count = ingest_historical_incidents(force=True)
                    st.success(f"✅ Seeded: {result['logs']} logs, {result['metrics']} metrics, "
                               f"{result['deployments']} deploys, {count} incidents in vectorstore")
                else:
                    resp = httpx.post(f"{API_BASE}/seed", json={}, timeout=60)
                    data = resp.json()
                    if data.get("success"):
                        r = data["data"]
                        st.success(f"✅ Seeded: {r['logs']} logs, {r['metrics']} metrics")
                    else:
                        st.error("Seed failed")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.markdown("#### 🏗️ Architecture")
    st.markdown("""
```
User Query
    │
Planner Agent
    │
Log Agent
    │
Metrics Agent
    │
Deployment Agent
    │
Historical Incident RAG
(ChromaDB + MiniLM)
    │
Root Cause Agent
    │
Final Report
```
""")

    st.divider()
    st.markdown("#### 🛠️ Tech Stack")
    st.markdown("""
- 🧠 **Gemini 1.5 Flash** (free tier)
- 🔗 **LangGraph** multi-agent
- 📚 **ChromaDB** vectorstore
- 🤗 **MiniLM-L6-v2** embeddings
- ⚡ **FastAPI** backend
- 📊 **DeepEval + RAGAS** evals
""")


# ── Main Header ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1 style="margin:0; font-size:2em;">🔍 AI Incident Investigation Agent</h1>
    <p style="margin:0.5rem 0 0 0; opacity:0.8;">
        Production-grade multi-agent system for automated Root Cause Analysis
    </p>
</div>
""", unsafe_allow_html=True)


# ── Query Input ──────────────────────────────────────────────────────────────
st.markdown("### 📝 Describe the Incident")

example_queries = [
    "Checkout latency increased 10x after deployment v3.8. CPU and memory are normal but error rate jumped to 8%.",
    "Payment gateway crashed with OutOfMemoryError after JDBC driver upgrade.",
    "Why did the auth service slow down after the JWT expiry config change?",
    "Notification service dropped 15000 messages after migrating from SQS to Kafka.",
]

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_area(
        "Incident Query",
        placeholder="e.g. Checkout latency spiked after deployment v3.8. Error rate went from 0.3% to 8.5%...",
        height=100,
        label_visibility="collapsed",
    )
with col2:
    st.markdown("**Quick examples:**")
    for i, ex in enumerate(example_queries):
        if st.button(f"Example {i+1}", key=f"ex_{i}", use_container_width=True):
            st.session_state["query_val"] = ex
            st.rerun()

# Apply example query if selected
if "query_val" in st.session_state and not query:
    query = st.session_state["query_val"]

run_btn = st.button(
    "🚀 Investigate Incident",
    type="primary",
    use_container_width=True,
    disabled=not query or not api_key,
)

if not api_key:
    st.warning("⚠️ Add your Gemini API key in the sidebar to start (it's free!)")

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_report, tab_agents, tab_metrics, tab_raw = st.tabs([
    "📋 Investigation Report",
    "🤖 Agent Trail",
    "📊 Metrics Dashboard",
    "🔩 Raw Data",
])

# ── Investigation Execution ──────────────────────────────────────────────────
if run_btn and query and api_key:
    # Progress tracking
    progress_container = st.container()
    with progress_container:
        st.markdown("### ⚙️ Investigation in progress...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        agent_steps = [
            ("planner", "📋 Planning investigation..."),
            ("log_agent", "📄 Analyzing application logs..."),
            ("metrics_agent", "📊 Detecting metric anomalies..."),
            ("deployment_agent", "🚀 Correlating deployments..."),
            ("rootcause_agent", "🧠 Synthesizing root cause..."),
            ("summarizer", "📝 Generating final report..."),
        ]

        step_containers = {}
        for step_id, step_label in agent_steps:
            step_containers[step_id] = st.empty()
            step_containers[step_id].markdown(f"⏳ {step_label}")

    # Track progress via callback
    completed_steps = []

    def progress_callback(node_name: str, state: dict):
        idx = [s[0] for s in agent_steps].index(node_name) if node_name in [s[0] for s in agent_steps] else 0
        progress = (idx + 1) / len(agent_steps)
        progress_bar.progress(progress)
        label = next((s[1] for s in agent_steps if s[0] == node_name), node_name)
        status_text.markdown(f"**✅ {label}**")
        step_containers[node_name].markdown(f"✅ {label}")
        completed_steps.append(node_name)

    try:
        with st.spinner(""):
            if STANDALONE:
                state = run_investigation(query, progress_callback=progress_callback)
            else:
                resp = httpx.post(
                    f"{API_BASE}/investigate",
                    json={"query": query},
                    timeout=300,
                )
                result = resp.json()
                if not result.get("success"):
                    st.error(f"Investigation failed: {result}")
                    st.stop()
                state = result
                # Mark all steps done
                for step_id, label in agent_steps:
                    step_containers[step_id].markdown(f"✅ {label}")
                progress_bar.progress(1.0)

        progress_container.empty()
        st.session_state["last_state"] = state
        st.success("✅ Investigation complete!")

    except Exception as e:
        st.error(f"❌ Investigation failed: {e}")
        st.exception(e)
        st.stop()

# ── Display Results ──────────────────────────────────────────────────────────
state = st.session_state.get("last_state", {})

if state:
    rca = state.get("rca", {})
    plan = state.get("plan", {})
    log_findings = state.get("log_findings", {})
    metrics_findings = state.get("metrics_findings", {})
    deployment_findings = state.get("deployment_findings", {})
    similar = state.get("similar_incidents", [])
    messages = state.get("messages", [])

    # ── Top KPI Row ──────────────────────────────────────────────────────────
    root_cause_data = rca.get("root_cause", {})
    confidence = root_cause_data.get("confidence_pct", 0)
    metrics_raw = metrics_findings.get("raw_summary", {})

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        conf_class = "confidence-high" if confidence >= 85 else ("confidence-medium" if confidence >= 65 else "confidence-low")
        st.metric("🎯 Confidence", f"{confidence}%")
    with kpi2:
        st.metric("⚡ Latency P99 (max)", f"{metrics_raw.get('latency_p99_max_ms', 'N/A')} ms")
    with kpi3:
        st.metric("🔴 Error Rate (max)", f"{metrics_raw.get('error_rate_max_pct', 'N/A')}%")
    with kpi4:
        suspect = deployment_findings.get("suspect_deployment", {})
        st.metric("🚀 Suspect Deploy", suspect.get("version", "N/A"))

    st.divider()

    # ── Tab: Report ──────────────────────────────────────────────────────────
    with tab_report:
        report = state.get("final_report", "")
        if report:
            st.markdown(report)
        else:
            st.info("Run an investigation to see the report.")

    # ── Tab: Agent Trail ─────────────────────────────────────────────────────
    with tab_agents:
        st.markdown("### 🤖 Multi-Agent Investigation Trail")

        agent_colors = {
            "planner": "#3498db",
            "log_agent": "#e74c3c",
            "metrics_agent": "#9b59b6",
            "deployment_agent": "#e67e22",
            "rootcause_agent": "#27ae60",
            "summarizer": "#1abc9c",
        }

        agent_icons = {
            "planner": "📋",
            "log_agent": "📄",
            "metrics_agent": "📊",
            "deployment_agent": "🚀",
            "rootcause_agent": "🧠",
            "summarizer": "📝",
        }

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            color = agent_colors.get(role, "#95a5a6")
            icon = agent_icons.get(role, "🤖")
            label = role.replace("_", " ").title()
            st.markdown(
                f"""<div style="border-left: 4px solid {color}; padding: 0.75rem 1rem; 
                margin: 0.4rem 0; border-radius: 0 8px 8px 0; background: #f8f9fa;">
                <strong>{icon} {label}</strong><br/><span style="color:#555">{content}</span>
                </div>""",
                unsafe_allow_html=True,
            )

        st.divider()

        # Show plan
        if plan:
            with st.expander("📋 Investigation Plan (Planner Agent)"):
                st.json(plan)

        # Show hypotheses
        alt_hypotheses = rca.get("alternative_hypotheses", [])
        if alt_hypotheses:
            with st.expander("🔄 Alternative Hypotheses"):
                for h in alt_hypotheses:
                    likelihood = h.get("likelihood", "unknown")
                    color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(likelihood, "⚪")
                    st.markdown(f"**{color} {h.get('hypothesis')}** — `{likelihood}` likelihood")
                    st.markdown(f"> {h.get('reasoning', '')}")

        # Similar incidents
        if similar:
            with st.expander(f"📚 Similar Historical Incidents ({len(similar)} found via RAG)"):
                for inc in similar:
                    m = inc.get("metadata", {})
                    similarity = inc.get("similarity_score", 0)
                    bar = "█" * int(similarity * 10) + "░" * (10 - int(similarity * 10))
                    st.markdown(f"**{m.get('title')}** ({m.get('date')})")
                    st.markdown(f"Similarity: `{bar}` {similarity:.0%}")
                    with st.expander("Full document"):
                        st.text(inc.get("document", ""))

    # ── Tab: Metrics Dashboard ───────────────────────────────────────────────
    with tab_metrics:
        st.markdown("### 📊 Live Metrics Dashboard")

        # Load raw metrics for charts
        try:
            if STANDALONE:
                metrics_data = load_metrics()
            else:
                resp = httpx.get(f"{API_BASE}/data/metrics", timeout=30)
                metrics_data = resp.json()
        except Exception:
            metrics_data = []

        if metrics_data:
            timestamps = [m["timestamp"][:16] for m in metrics_data]
            latency = [m["latency_p99_ms"] for m in metrics_data]
            errors = [m["error_rate_pct"] for m in metrics_data]
            db_conn = [m["db_connection_pool_pct"] for m in metrics_data]
            cpu = [m["cpu_pct"] for m in metrics_data]

            # Chart 1: Latency
            fig_latency = go.Figure()
            fig_latency.add_trace(go.Scatter(
                x=timestamps, y=latency, mode="lines+markers",
                name="Latency P99 (ms)", line=dict(color="#e74c3c", width=2),
                fill="tozeroy", fillcolor="rgba(231,76,60,0.1)",
            ))
            fig_latency.add_hline(y=2000, line_dash="dash", line_color="orange",
                                  annotation_text="Alert threshold (2000ms)")
            fig_latency.update_layout(
                title="Latency P99 over time",
                xaxis_title="Time",
                yaxis_title="ms",
                height=300,
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig_latency, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                # Chart 2: Error Rate
                fig_err = go.Figure()
                fig_err.add_trace(go.Scatter(
                    x=timestamps, y=errors, mode="lines",
                    name="Error Rate %", line=dict(color="#9b59b6", width=2),
                    fill="tozeroy", fillcolor="rgba(155,89,182,0.1)",
                ))
                fig_err.add_hline(y=2.0, line_dash="dash", line_color="red",
                                  annotation_text="Alert (2%)")
                fig_err.update_layout(title="Error Rate %", height=260, margin=dict(t=40, b=20))
                st.plotly_chart(fig_err, use_container_width=True)

            with col2:
                # Chart 3: DB Connection Pool
                fig_db = go.Figure()
                fig_db.add_trace(go.Scatter(
                    x=timestamps, y=db_conn, mode="lines",
                    name="DB Pool %", line=dict(color="#e67e22", width=2),
                    fill="tozeroy", fillcolor="rgba(230,126,34,0.1)",
                ))
                fig_db.add_hline(y=80, line_dash="dash", line_color="red",
                                 annotation_text="Saturation (80%)")
                fig_db.update_layout(title="DB Connection Pool %", height=260, margin=dict(t=40, b=20))
                st.plotly_chart(fig_db, use_container_width=True)

            # Chart 4: CPU
            fig_cpu = go.Figure()
            fig_cpu.add_trace(go.Bar(
                x=timestamps[::4], y=cpu[::4],
                name="CPU %", marker_color="#3498db",
            ))
            fig_cpu.update_layout(title="CPU Usage %", height=200, margin=dict(t=40, b=20))
            st.plotly_chart(fig_cpu, use_container_width=True)

        else:
            st.info("Seed demo data first to see metrics charts.")

    # ── Tab: Raw Data ────────────────────────────────────────────────────────
    with tab_raw:
        st.markdown("### 🔩 Raw Agent Findings")

        with st.expander("📄 Log Agent Findings"):
            st.json(log_findings)
        with st.expander("📊 Metrics Agent Findings"):
            st.json(metrics_findings)
        with st.expander("🚀 Deployment Agent Findings"):
            st.json(deployment_findings)
        with st.expander("🧠 Root Cause (full JSON)"):
            st.json(rca)

else:
    with tab_report:
        st.markdown("""
        ### 👋 Welcome to AI Incident Investigator

        This tool uses a **multi-agent LangGraph pipeline** to automatically investigate
        production incidents by analyzing logs, metrics, and deployment history.

        **To get started:**
        1. Add your **Gemini API key** in the sidebar (free at [aistudio.google.com](https://aistudio.google.com/app/apikey))
        2. Click **🌱 Seed Demo Incident Data** to load synthetic data
        3. Type or select an incident query
        4. Click **🚀 Investigate Incident**

        **What the agents do:**
        | Agent | Role |
        |-------|------|
        | 📋 Planner | Analyzes your query, creates investigation plan |
        | 📄 Log Agent | Scans error logs, identifies patterns |
        | 📊 Metrics Agent | Detects latency/error/resource anomalies |
        | 🚀 Deployment Agent | Correlates deployments with incident timeline |
        | 🧠 Root Cause Agent | Synthesizes findings + RAG historical search |
        | 📝 Summarizer | Generates final markdown RCA report |
        """)
