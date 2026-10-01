"""
LangGraph workflow for IncidentIQ.

Current architecture:

    START
      ↓
    Investigation Orchestrator
      ↓
    Final Investigation Result
      ↓
    END

The orchestrator internally handles:

    Investigation Agent
          ↓
      Tool Selection
          ↓
      Evidence Collection
          ↓
       Reasoning
          ↓
      Next Investigation
          ↓
      Final Synthesis
"""

from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from loguru import logger

from agents.orchestrator import run_investigation_loop


# ── Investigation State ─────────────────────────────────────────────────────

class InvestigationState(TypedDict):
    """
    Shared state of the IncidentIQ investigation.

    The state represents the knowledge collected during
    the investigation rather than a fixed sequence of agents.
    """

    # Original incident reported by the user
    incident: str

    # Things discovered during the investigation
    observations: list

    # Evidence collected from investigation tools
    evidence: list

    # Possible explanations for the incident
    hypotheses: list

    # Investigation tools/sources already used
    tools_used: list

    # Information still required
    evidence_gaps: list

    # Overall investigation confidence
    confidence: float

    # Why the investigation stopped
    stop_reason: str

    # Final RCA, solution, actions and prevention
    final_result: dict


# ── Orchestrator Node ───────────────────────────────────────────────────────

def run_orchestrator_node(
    state: InvestigationState,
    config=None,
) -> dict:
    """
    Execute the complete IncidentIQ investigation loop.

    The orchestrator internally manages:
        - Investigation Agent
        - Dynamic tool selection
        - Evidence collection
        - Iterative investigation
        - Final synthesis
    """

    incident = state["incident"]

    logger.info(
        "[Workflow] Starting Investigation Orchestrator..."
    )

    # ---------------------------------------------------------
    # Retrieve optional progress callback from LangGraph config
    # ---------------------------------------------------------

    progress_callback = None

    if config:

        configurable = config.get(
            "configurable",
            {}
        )

        progress_callback = configurable.get(
            "progress_callback"
        )

    # ---------------------------------------------------------
    # Run Investigation Orchestrator
    # ---------------------------------------------------------

    result = run_investigation_loop(
        incident=incident,
        progress_callback=progress_callback,
    )

    return {
        "incident": result["incident"],
        "observations": result["observations"],
        "evidence": result["evidence"],
        "hypotheses": result["hypotheses"],
        "tools_used": result["tools_used"],
        "evidence_gaps": result["evidence_gaps"],
        "confidence": result["confidence"],
        "stop_reason": result["stop_reason"],
        "final_result": result["final_result"],
    }


# ── Build Graph ─────────────────────────────────────────────────────────────

def build_workflow():
    """
    Build the IncidentIQ LangGraph workflow.

    LangGraph is now responsible only for the outer workflow.

    The actual investigation logic is handled by the
    Investigation Orchestrator.
    """

    graph = StateGraph(InvestigationState)

    # Single high-level investigation node.
    graph.add_node(
        "investigation_orchestrator",
        run_orchestrator_node
    )

    graph.add_edge(
        START,
        "investigation_orchestrator"
    )

    graph.add_edge(
        "investigation_orchestrator",
        END
    )

    return graph.compile()


# ── Run Investigation ───────────────────────────────────────────────────────

def run_investigation(
    query: str,
    progress_callback=None,
) -> dict:
    """
    Run the complete IncidentIQ investigation workflow.

    Args:
        query:
            Natural-language description of the incident.

        progress_callback:
            Optional callback receiving:
                (step_name, current_state)

    Returns:
        Final investigation state.
    """

    logger.info(
        f"Starting incident investigation for: '{query[:80]}'"
    )

    workflow = build_workflow()

    initial_state = {
        "incident": query,
        "observations": [],
        "evidence": [],
        "hypotheses": [],
        "tools_used": [],
        "evidence_gaps": [],
        "confidence": 0.0,
        "stop_reason": "max_iterations_reached",
        "final_result": {},
    }

    final_state = initial_state.copy()

    # ---------------------------------------------------------
    # LangGraph configuration
    # ---------------------------------------------------------

    config = {
        "configurable": {
            "progress_callback": progress_callback
        }
    }

    try:

        for step_output in workflow.stream(
            initial_state,
            config=config,
            stream_mode="updates",
        ):

            for node_name, node_state in step_output.items():

                final_state.update(node_state)

                logger.info(
                    f"✓ Completed node: {node_name}"
                )

                # LangGraph-level progress notification.
                if progress_callback:

                    progress_callback(
                        node_name,
                        final_state,
                    )

    except Exception as e:

        logger.error(
            f"Workflow error: {e}"
        )

        raise

    logger.info(
        "Investigation complete."
    )

    return final_state