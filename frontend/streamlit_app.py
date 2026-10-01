"""
IncidentIQ — Streamlit frontend.

Production mode:
    streamlit run frontend/streamlit_app.py
    Requires the FastAPI backend on API_BASE (default: http://localhost:8000)

Local standalone mode:
    Set STANDALONE=true
    This runs the investigation workflow inside Streamlit for development only.

Developer tools:
    Set SHOW_DEV_TOOLS=true to show synthetic demo-data seeding controls.
"""

import os
import sys
API_KEY = os.getenv("API_KEY", "")
# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")

STANDALONE = os.getenv("STANDALONE", "false").lower() == "true"
SHOW_DEV_TOOLS = os.getenv("SHOW_DEV_TOOLS", "false").lower() == "true"
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

if STANDALONE:
    sys.path.insert(0, BACKEND)
    sys.path.insert(0, ROOT)

import streamlit as st
import plotly.graph_objects as go

if STANDALONE:
    from graph.workflow import run_investigation
    from utils.data_generator import seed_data
    from utils.parser import load_metrics
    from config import DATA_DIR
else:
    import httpx


# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="IncidentIQ",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def as_list(value):
    """Normalize strings, lists and unexpected values for clean rendering."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def render_bullets(items):
    """Render a list as clean markdown bullets."""
    for item in as_list(items):
        if isinstance(item, dict):
            text = item.get("text") or item.get("reasoning") or str(item)
        else:
            text = str(item)
        st.markdown(f"- {text}")


def confidence_display(confidence):
    if isinstance(confidence, (int, float)):
        return f"{confidence:.0%}" if confidence <= 1 else f"{confidence:.0f}%"
    return str(confidence or "Unknown")


def severity_class(severity):
    value = str(severity or "unknown").lower()
    if value in {"critical", "high"}:
        return "severity-high"
    if value == "medium":
        return "severity-medium"
    return "severity-low"


def call_backend(method, path, **kwargs):
    """Call the FastAPI backend with a consistent timeout/error message."""

    try:
        with httpx.Client(timeout=kwargs.pop("timeout", 60)) as client:
            response = client.request(
                method,
                f"{API_BASE}{path}",
                **kwargs,
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPError as exc:
        raise RuntimeError(f"Backend request failed: {exc}") from exc


def get_metrics_data():
    if STANDALONE:
        return load_metrics()
    data = call_backend("GET","/api/v1/data/metrics",timeout=30,)
    return data if isinstance(data, list) else []


# -----------------------------------------------------------------------------
# Styling
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
    /* Page rhythm */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* Hero */
    .main-header {
        background: linear-gradient(135deg, #171a2b 0%, #20294a 100%);
        padding: 1.6rem 1.8rem;
        border-radius: 14px;
        margin-bottom: 1.4rem;
        border: 1px solid rgba(255,255,255,0.08);
    }

    .main-header h1 {
        margin: 0;
        font-size: 2rem;
    }

    .main-header p {
        margin: 0.45rem 0 0;
        opacity: 0.78;
        font-size: 1rem;
    }

    /* Section cards */
    .root-cause-card {
        padding: 1.15rem 1.25rem;
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 12px;
        margin: 0.6rem 0 1rem;
    }

    .severity-badge {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin-left: 0.4rem;
    }

    .severity-high {
        background: rgba(220, 53, 69, 0.16);
        color: #ff7b87;
    }

    .severity-medium {
        background: rgba(255, 193, 7, 0.16);
        color: #ffc857;
    }

    .severity-low {
        background: rgba(40, 167, 69, 0.16);
        color: #65d681;
    }

    .muted {
        color: #8f96a3;
        font-size: 0.9rem;
    }

    /* Reduce visual noise from Streamlit containers */
    div[data-testid="stMetric"] {
        padding: 0.7rem 0.8rem;
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 10px;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem;
    }

    /* Primary action */
    div.stButton > button[kind="primary"] {
        min-height: 3rem;
        font-weight: 700;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.5rem;
    }

    /* Avoid excessive whitespace around tabs */
    button[data-baseweb="tab"] {
        font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔎 IncidentIQ")
    st.caption("Evidence-driven incident investigation")
    st.divider()

    st.markdown("#### 🔐 Security")
    st.info("Gemini API access is managed by the backend. Secrets are not exposed in the UI.")

    if SHOW_DEV_TOOLS:
        st.divider()
        st.markdown("#### 🧪 Developer Tools")
        st.caption("Development-only controls. Keep hidden in production.")

        if st.button("🌱 Seed Demo Incident Data", use_container_width=True):
            with st.spinner("Seeding synthetic incident data..."):
                try:
                    if STANDALONE:
                        result = seed_data(DATA_DIR)
                        st.success(
                            f"Seeded {result['logs']} logs, "
                            f"{result['metrics']} metrics and "
                            f"{result['deployments']} deployments."
                        )
                    else:
                        data = call_backend("POST","/api/v1/seed",json={},timeout=60,)
                        if data.get("success"):
                            seeded = data.get("result", {})
                            st.success(
                                f"Seeded {seeded.get('logs', 0)} logs, "
                                f"{seeded.get('metrics', 0)} metrics and "
                                f"{seeded.get('deployments', 0)} deployments."
                            )
                        else:
                            st.error("Demo-data seeding failed.")
                except Exception as exc:
                    st.error(str(exc))

    st.divider()
    st.markdown("#### 🧭 How IncidentIQ works")
    st.markdown(
        """
```text
Incident
   ↓
Investigation Agent
   ↓
Choose evidence source
   ↓
Logs / Metrics / Deployments
   ↓
Evidence + Hypotheses
   ↓
Final Synthesis
   ↓
RCA + Solution + Prevention
```
"""
    )

    st.divider()
    st.markdown("#### 🛠️ Tech Stack")
    st.markdown(
        """
- 🧠 **Gemini 3.5 Flash** — reasoning & synthesis
- 🔗 **LangGraph** — investigation orchestration
- ⚡ **FastAPI** — backend API
- 📊 **Plotly** — diagnostics
- 📚 **RAG / ChromaDB** — historical incidents (extensible)
- 🧪 **DeepEval + RAGAS** — evaluation
"""
    )

    st.caption("Architecture: single Investigation Agent + evidence tools")


# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown(
    """
<div class="main-header">
    <h1>🔎 IncidentIQ</h1>
    <p>Investigate production incidents, correlate evidence, and generate an explainable RCA.</p>
</div>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Incident input
# -----------------------------------------------------------------------------
st.markdown("### 📝 Describe the incident")

example_queries = [
    "Checkout latency increased 10x after deployment v3.8. CPU and memory are normal but error rate jumped to 8%.",
    "Payment gateway crashed with OutOfMemoryError after JDBC driver upgrade.",
    "Why did the auth service slow down after the JWT expiry config change?",
    "Notification service dropped 15000 messages after migrating from SQS to Kafka.",
]

col1, col2 = st.columns([3.2, 1])

with col1:
    query = st.text_area(
        "Incident Query",
        value=st.session_state.get("query_val", ""),
        placeholder="Describe what happened, when it started, and any symptoms you observed...",
        height=120,
        label_visibility="collapsed",
    )

with col2:
    st.markdown("**Quick examples**")
    for i, example in enumerate(example_queries):
        if st.button(f"Example {i + 1}", key=f"example_{i}", use_container_width=True):
            st.session_state["query_val"] = example
            st.rerun()

run_btn = st.button(
    "🚀 Investigate Incident",
    type="primary",
    use_container_width=True,
    disabled=not query.strip(),
)


# -----------------------------------------------------------------------------
# Result tabs
# -----------------------------------------------------------------------------
tab_report, tab_evidence, tab_trace, tab_diagnostics = st.tabs(
    [
        "📋 Report",
        "🔍 Evidence",
        "🧠 Investigation Trace",
        "📊 Diagnostics",
    ]
)


# -----------------------------------------------------------------------------
# Investigation execution
# -----------------------------------------------------------------------------
if run_btn and query.strip():
    progress_container = st.container()

    with progress_container:
        st.markdown("### ⚙️ Investigation in progress")
        progress_bar = st.progress(0)
        status_text = st.empty()
        trail_container = st.empty()
        progress_steps = []

        status_text.markdown("**🧠 Investigation Agent is analyzing the incident...**")

    def render_live_trail():
        if progress_steps:
            trail_container.markdown(
                "#### Investigation Trail\n\n"
                + "\n\n".join(f"✅ {step}" for step in progress_steps)
            )

    def progress_callback(step_name: str, state: dict):
        iteration = state.get("iteration", len(progress_steps) + 1)

        tool_labels = {
            "query_logs": "📄 Querying application logs...",
            "query_metrics": "📊 Analyzing service metrics...",
            "get_deployments": "🚀 Checking deployment history...",
            "inspect_api": "🌐 Inspecting API traffic...",
            "inspect_database": "🗄️ Inspecting database health...",
            "inspect_infrastructure": "🏗️ Inspecting infrastructure...",
            "inspect_security": "🔐 Inspecting security signals...",
            "search_historical_incidents": "📚 Searching historical incidents...",
        }

        if step_name == "investigation":
            status_text.markdown(
                f"**🧠 Investigation Agent — deciding what to investigate next "
                f"(iteration {iteration})...**"
            )
            progress_steps.append(f"Investigation Agent — iteration {iteration}")

        elif step_name in tool_labels:
            status_text.markdown(f"**{tool_labels[step_name]}**")
            progress_steps.append(f"{step_name}()")

        elif step_name == "synthesis":
            status_text.markdown("**📝 Synthesizing root cause, solution and prevention...**")
            progress_steps.append("Final synthesis")

        elif step_name == "investigation_orchestrator":
            status_text.markdown("**✅ Investigation workflow completed**")

        progress_bar.progress(min(0.95, 0.10 + len(progress_steps) * 0.12))
        render_live_trail()

    try:
        if STANDALONE:
            state = run_investigation(query.strip(), progress_callback=progress_callback)
        else:
            result = call_backend(
                "POST",
                "/api/v1/incidents/investigate",
                json={"query": query.strip()},
                headers={"X-API-Key": API_KEY},
                timeout=300,
            )
            if not result.get("success"):
                raise RuntimeError(f"Investigation failed: {result}")
            state = result

        progress_bar.progress(1.0)
        status_text.markdown("**✅ Investigation complete — final RCA generated.**")
        progress_container.empty()

        st.session_state["last_state"] = state
        st.session_state["query_val"] = query.strip()
        st.rerun()

    except Exception as exc:
        progress_container.empty()
        st.error(f"❌ Investigation failed: {exc}")
        st.exception(exc)


# -----------------------------------------------------------------------------
# Display latest investigation
# -----------------------------------------------------------------------------
state = st.session_state.get("last_state", {})

if state:
    observations = as_list(state.get("observations", []))
    evidence = as_list(state.get("evidence", []))
    hypotheses = as_list(state.get("hypotheses", []))
    tools_used = as_list(state.get("tools_used", []))
    evidence_gaps = as_list(state.get("evidence_gaps", []))
    confidence = state.get("confidence", 0)
    final_result = state.get("final_result") or {}

    # -------------------------------------------------------------------------
    # KPI row
    # -------------------------------------------------------------------------
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric("🎯 Confidence", confidence_display(confidence))

    with kpi2:
        st.metric("🛠️ Tools Used", len(tools_used))

    with kpi3:
        st.metric("🔍 Evidence", len(evidence))

    with kpi4:
        st.metric("⚠️ Evidence Gaps", len(evidence_gaps))

    st.divider()

    # -------------------------------------------------------------------------
    # Report
    # -------------------------------------------------------------------------
    with tab_report:
        st.markdown("### 📋 Investigation Report")

        if final_result:
            root_cause = final_result.get("probable_root_cause", "")
            severity = final_result.get("severity", "")
            solution = final_result.get("probable_solution", "")
            actions = final_result.get("immediate_actions", [])
            prevention = final_result.get("long_term_prevention", [])
            supporting = final_result.get("supporting_evidence", [])
            alternatives = final_result.get("alternative_hypotheses", [])

            if root_cause:
                severity_html = ""
                if severity:
                    severity_html = (
                        f'<span class="severity-badge {severity_class(severity)}">'
                        f"{str(severity).upper()}</span>"
                    )

                st.markdown(
                    f"""
<div class="root-cause-card">
    <div class="muted">PROBABLE ROOT CAUSE {severity_html}</div>
    <div style="font-size:1.25rem; font-weight:700; margin-top:0.55rem;">
        {root_cause}
    </div>
</div>
""",
                    unsafe_allow_html=True,
                )

            if supporting:
                st.markdown("#### 🔍 Why IncidentIQ believes this")
                render_bullets(supporting)

            if solution:
                st.markdown("#### 🛠️ Probable Solution")
                if isinstance(solution, (list, tuple)):
                    render_bullets(solution)
                else:
                    st.info(str(solution))

            if actions:
                st.markdown("#### ⚡ Immediate Actions")
                render_bullets(actions)

            if prevention:
                st.markdown("#### 🛡️ Long-Term Prevention")
                render_bullets(prevention)

            if alternatives:
                with st.expander("🔄 Alternative hypotheses"):
                    for item in as_list(alternatives):
                        if isinstance(item, dict):
                            st.markdown(
                                f"- **{item.get('hypothesis', 'Unknown')}** — "
                                f"{item.get('reasoning', '')}"
                            )
                        else:
                            st.markdown(f"- {item}")

            st.caption(
                "RCA is the most likely explanation supported by the available evidence; "
                "it does not automatically prove causality."
            )
        else:
            st.info("The investigation completed without a final synthesis.")

    # -------------------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------------------
    with tab_evidence:
        st.markdown("### 🔍 Collected Evidence")
        st.caption("Detailed evidence collected by the investigation tools.")

        if evidence:
            for i, item in enumerate(evidence, 1):
                with st.expander(f"Evidence {i}", expanded=(i <= 3)):
                    if isinstance(item, dict):
                        st.json(item)
                    else:
                        st.write(item)
        else:
            st.info("No evidence was collected.")

    # -------------------------------------------------------------------------
    # Investigation trace
    # -------------------------------------------------------------------------
    with tab_trace:
        st.markdown("### 🧠 Investigation Trace")
        st.caption("How the Investigation Agent selected evidence sources during this run.")

        if tools_used:
            for i, tool in enumerate(tools_used, 1):
                st.markdown(f"**{i}.** `{tool}()`")
        else:
            st.info("No investigation tools were recorded.")

        if observations:
            st.divider()
            st.markdown("#### 👀 Key Observations")
            render_bullets(observations)

        if hypotheses:
            st.divider()
            st.markdown("#### 💡 Hypotheses")
            render_bullets(hypotheses)

        if evidence_gaps:
            st.divider()
            st.markdown("#### ⚠️ Evidence Gaps")
            for gap in evidence_gaps:
                st.warning(str(gap))

    # -------------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------------
    with tab_diagnostics:
        st.markdown("### 📊 Diagnostics")
        st.caption("Operational metrics available to support the investigation.")

        try:
            metrics_data = get_metrics_data()
        except Exception as exc:
            metrics_data = []
            st.warning(f"Could not load metrics: {exc}")

        if metrics_data:
            timestamps = [str(m.get("timestamp", ""))[:16] for m in metrics_data]
            latency = [m.get("latency_p99_ms", 0) for m in metrics_data]
            errors = [m.get("error_rate_pct", 0) for m in metrics_data]
            db_conn = [m.get("db_connection_pool_pct", 0) for m in metrics_data]
            cpu = [m.get("cpu_pct", 0) for m in metrics_data]

            fig_latency = go.Figure()
            fig_latency.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=latency,
                    mode="lines+markers",
                    name="P99 latency",
                )
            )
            fig_latency.add_hline(
                y=2000,
                line_dash="dash",
                annotation_text="Alert: 2000 ms",
            )
            fig_latency.update_layout(
                title="P99 Latency",
                xaxis_title="Time",
                yaxis_title="Milliseconds",
                height=320,
                margin=dict(t=55, b=35, l=45, r=20),
            )
            st.plotly_chart(fig_latency, use_container_width=True)

            c1, c2 = st.columns(2)

            with c1:
                fig_err = go.Figure()
                fig_err.add_trace(
                    go.Scatter(x=timestamps, y=errors, mode="lines", name="Error rate")
                )
                fig_err.add_hline(
                    y=2.0,
                    line_dash="dash",
                    annotation_text="Alert: 2%",
                )
                fig_err.update_layout(
                    title="Error Rate",
                    xaxis_title="Time",
                    yaxis_title="Percent",
                    height=280,
                    margin=dict(t=55, b=35, l=45, r=20),
                )
                st.plotly_chart(fig_err, use_container_width=True)

            with c2:
                fig_db = go.Figure()
                fig_db.add_trace(
                    go.Scatter(x=timestamps, y=db_conn, mode="lines", name="DB pool")
                )
                fig_db.add_hline(
                    y=80,
                    line_dash="dash",
                    annotation_text="Saturation: 80%",
                )
                fig_db.update_layout(
                    title="DB Connection Pool",
                    xaxis_title="Time",
                    yaxis_title="Percent",
                    height=280,
                    margin=dict(t=55, b=35, l=45, r=20),
                )
                st.plotly_chart(fig_db, use_container_width=True)

            fig_cpu = go.Figure()
            fig_cpu.add_trace(
                go.Bar(
                    x=timestamps[::4],
                    y=cpu[::4],
                    name="CPU",
                )
            )
            fig_cpu.update_layout(
                title="CPU Usage",
                xaxis_title="Time",
                yaxis_title="Percent",
                height=250,
                margin=dict(t=55, b=35, l=45, r=20),
            )
            st.plotly_chart(fig_cpu, use_container_width=True)
        else:
            st.info("No metrics are available yet. Seed demo data in developer mode or connect a metrics source.")

else:
    # -------------------------------------------------------------------------
    # Empty state
    # -------------------------------------------------------------------------
    with tab_report:
        st.markdown("### 👋 Start an investigation")
        st.markdown(
            """
IncidentIQ investigates an incident by selecting the most useful evidence source,
collecting observations, and then synthesizing a probable root cause.

**Typical investigation flow**

1. Describe the incident and symptoms.
2. The Investigation Agent chooses what to inspect next.
3. Evidence is collected from available tools such as logs, metrics and deployments.
4. IncidentIQ correlates the evidence and produces an RCA.
5. The report provides a probable solution, immediate actions and prevention steps.
"""
        )

        st.info("💡 Start with a specific symptom, such as increased latency, elevated errors, or a failure after deployment.")