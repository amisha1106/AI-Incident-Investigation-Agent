"""
LangGraph multi-agent workflow for incident investigation.

Graph structure:
    START → planner → [log_agent, metrics_agent, deployment_agent] → rootcause → summarizer → END

All data-collection agents run sequentially (LangGraph handles state passing).
Future: can be parallelized with Send() API.
"""

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from loguru import logger

from agents.planner import run_planner
from agents.log_agent import run_log_agent
from agents.metrics_agent import run_metrics_agent
from agents.deployment_agent import run_deployment_agent
from agents.rootcause_agent import run_rootcause_agent
from agents.summarizer import run_summarizer


# ── State Schema ────────────────────────────────────────────────────────────
class IncidentState(TypedDict):
    query: str
    plan: dict
    log_findings: dict
    metrics_findings: dict
    deployment_findings: dict
    rca: dict
    similar_incidents: list
    final_report: str
    messages: list[dict]


# ── Build Graph ──────────────────────────────────────────────────────────────
def build_workflow() -> StateGraph:
    graph = StateGraph(IncidentState)

    # Register nodes
    graph.add_node("planner", run_planner)
    graph.add_node("log_agent", run_log_agent)
    graph.add_node("metrics_agent", run_metrics_agent)
    graph.add_node("deployment_agent", run_deployment_agent)
    graph.add_node("rootcause_agent", run_rootcause_agent)
    graph.add_node("summarizer", run_summarizer)

    # Define edges (sequential pipeline)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "log_agent")
    graph.add_edge("log_agent", "metrics_agent")
    graph.add_edge("metrics_agent", "deployment_agent")
    graph.add_edge("deployment_agent", "rootcause_agent")
    graph.add_edge("rootcause_agent", "summarizer")
    graph.add_edge("summarizer", END)

    return graph.compile()


def run_investigation(query: str, progress_callback=None) -> dict:
    """
    Run the full incident investigation workflow.

    Args:
        query: Natural language description of the incident
        progress_callback: Optional callable(step_name, state) for streaming progress

    Returns:
        Final state with all findings and the markdown report
    """
    logger.info(f"Starting incident investigation for: '{query[:80]}'")

    workflow = build_workflow()

    initial_state = {
        "query": query,
        "plan": {},
        "log_findings": {},
        "metrics_findings": {},
        "deployment_findings": {},
        "rca": {},
        "similar_incidents": [],
        "final_report": "",
        "messages": [],
    }

    steps = [
        "planner",
        "log_agent",
        "metrics_agent",
        "deployment_agent",
        "rootcause_agent",
        "summarizer",
    ]

    # Stream execution step by step
    final_state = initial_state.copy()
    try:
        for step_output in workflow.stream(initial_state, stream_mode="updates"):
            for node_name, node_state in step_output.items():
                final_state.update(node_state)
                logger.info(f"✓ Completed node: {node_name}")
                if progress_callback:
                    progress_callback(node_name, final_state)
    except Exception as e:
        logger.error(f"Workflow error: {e}")
        raise

    logger.info("Investigation complete.")
    return final_state
