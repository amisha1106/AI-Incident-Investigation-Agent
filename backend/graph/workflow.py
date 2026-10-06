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


class InvestigationState(TypedDict):
    """
    Shared state of the IncidentIQ investigation.
    """

    # API request correlation identifier
    request_id: str | None

    # Background job identifier
    job_id: str | None

    # Unique investigation identifier
    investigation_id: str

    # Original incident
    incident: str

    # Things discovered
    observations: list

    # Evidence collected
    evidence: list

    # Possible explanations
    hypotheses: list

    # Investigation tools/sources already used
    tools_used: list

    # Information still required
    evidence_gaps: list

    # Overall investigation confidence
    confidence: float

    # Why investigation stopped
    stop_reason: str

    # Final RCA, solution, actions and prevention
    final_result: dict


def run_orchestrator_node(
    state: InvestigationState,
    config=None,
) -> dict:
    """
    Execute the complete IncidentIQ investigation loop.
    """

    incident = state["incident"]

    logger.info(
        "[Workflow] Starting Investigation Orchestrator..."
    )

    # ---------------------------------------------------------
    # Retrieve optional progress callback
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
    # Correlation identifiers
    # ---------------------------------------------------------

    request_id = state.get(
        "request_id"
    )

    job_id = state.get(
        "job_id"
    )

    # ---------------------------------------------------------
    # Run Investigation Orchestrator
    # ---------------------------------------------------------

    result = run_investigation_loop(
        incident=incident,
        progress_callback=progress_callback,
        request_id=request_id,
        job_id=job_id,
    )

    return {
        "request_id": result.get(
            "request_id",
            request_id,
        ),
        "job_id": result.get(
            "job_id",
            job_id,
        ),
        "investigation_id": result[
            "investigation_id"
        ],
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


def build_workflow():
    """
    Build the IncidentIQ LangGraph workflow.

    LangGraph is responsible only for the outer workflow.

    Investigation logic is handled by the
    Investigation Orchestrator.
    """

    graph = StateGraph(InvestigationState)

    graph.add_node(
        "investigation_orchestrator",
        run_orchestrator_node,
    )

    graph.add_edge(
        START,
        "investigation_orchestrator",
    )

    graph.add_edge(
        "investigation_orchestrator",
        END,
    )

    return graph.compile()


def run_investigation(
    query: str,
    progress_callback=None,
    request_id: str | None = None,
    job_id: str | None = None,
) -> dict:
    """
    Run the complete IncidentIQ investigation workflow.

    Args:
        query:
            Natural-language description of the incident.

        progress_callback:
            Optional callback receiving:
                (step_name, current_state)

        request_id:
            API request correlation identifier.

        job_id:
            Background investigation job identifier.

    Returns:
        Final investigation state.
    """

    logger.info(
        f"Starting incident investigation for: '{query[:80]}'"
    )

    workflow = build_workflow()

    initial_state = {
        "request_id": request_id,
        "job_id": job_id,
        "investigation_id": "",
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
            "progress_callback": progress_callback,
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