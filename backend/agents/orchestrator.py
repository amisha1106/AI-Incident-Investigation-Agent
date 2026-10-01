"""
IncidentIQ Investigation Orchestrator.

Runs the investigation loop:

    Reason → Select Tool → Collect Evidence → Reason Again
                                      ↓
                              Final Synthesis
"""

from loguru import logger

from agents.investigation_agent import choose_next_tool
from agents.final_synthesis import run_final_synthesis

from tools.investigation_tools import (
    query_logs,
    query_metrics,
    get_deployments,
    inspect_api,
    inspect_database,
    inspect_infrastructure,
    inspect_security,
    search_historical_incidents,
)
import time
from observability.metrics import (
    record_investigation_started,
    record_investigation_completed,
    record_investigation_failed,
    record_tool_usage,
)


MAX_ITERATIONS = 10


TOOLS = {
    "query_logs": query_logs,
    "query_metrics": query_metrics,
    "get_deployments": get_deployments,
    "inspect_api": inspect_api,
    "inspect_database": inspect_database,
    "inspect_infrastructure": inspect_infrastructure,
    "inspect_security": inspect_security,
    "search_historical_incidents": search_historical_incidents,
}


def _deduplicate_items(items: list) -> list:
    """
    Remove duplicate evidence/observations/hypotheses/gaps
    while preserving the original order.
    """
    seen = set()
    unique_items = []

    for item in items:
        if item is None:
            continue

        if isinstance(item, dict):
            key = str(sorted(item.items()))
        else:
            key = str(item).strip().lower()

        if not key or key in seen:
            continue

        seen.add(key)
        unique_items.append(item)

    return unique_items


def _deduplicate_evidence_gaps(gaps: list) -> list:
    """
    Normalize and deduplicate evidence gaps collected
    from multiple investigation tools.
    """

    canonical = {
        "Database-level query execution plans are unavailable.":
            "Database query execution plans are unavailable.",

        "Individual database query execution plans are unavailable.":
            "Database query execution plans are unavailable.",

        "Distributed tracing information is unavailable.":
            "Distributed tracing is unavailable.",

        "Distributed request traces are unavailable.":
            "Distributed tracing is unavailable.",
    }

    deduplicated = []
    seen = set()

    for gap in gaps:

        text = str(gap).strip()

        if not text:
            continue

        normalized = canonical.get(
            text,
            text
        )

        key = normalized.lower()

        if key not in seen:
            seen.add(key)
            deduplicated.append(normalized)

    return deduplicated


def run_investigation_loop(
    incident: str,
    progress_callback=None,
) -> dict:
    """
    Run the complete IncidentIQ investigation.

    The Investigation Agent dynamically selects tools,
    collects evidence, and finally passes the collected
    evidence to the Final Synthesis Agent.
    """

    logger.info(
        f"[Orchestrator] Starting investigation: {incident[:80]}"
    )

    # ---------------------------------------------------------
    # Observability: investigation started
    # ---------------------------------------------------------

    record_investigation_started()
    start_time = time.perf_counter()

    observations = []
    evidence = []
    hypotheses = []
    tools_used = []
    evidence_gaps = []
    confidence = 0.0

    try:

        # -----------------------------------------------------
        # Investigation Loop
        # -----------------------------------------------------

        stop_reason = "max_iterations_reached"

        for iteration in range(1, MAX_ITERATIONS + 1):

            logger.info(
                f"[Orchestrator] Investigation iteration {iteration}"
            )

            # -------------------------------------------------
            # Notify frontend: Investigation Agent is reasoning
            # -------------------------------------------------

            if progress_callback:
                progress_callback(
                    "investigation",
                    {
                        "iteration": iteration,
                        "observations": observations,
                        "evidence": evidence,
                        "hypotheses": hypotheses,
                        "tools_used": tools_used,
                        "evidence_gaps": evidence_gaps,
                        "confidence": confidence,
                    },
                )

            # -------------------------------------------------
            # Investigation Agent selects next action
            # -------------------------------------------------

            decision = choose_next_tool(
                incident=incident,
                observations=observations,
                evidence=evidence,
                hypotheses=hypotheses,
                tools_used=tools_used,
                evidence_gaps=evidence_gaps,
            )

            action = decision.get("next_action")

            logger.info(
                f"[Orchestrator] Agent selected: {action}"
            )

            # -------------------------------------------------
            # Agent decides investigation is complete
            # -------------------------------------------------

            if action == "finish":

                stop_reason = "agent_finished"

                logger.info(
                    "[Orchestrator] Investigation finished by agent."
                )

                break

            # -------------------------------------------------
            # Agent decides evidence is insufficient
            # -------------------------------------------------

            if action == "insufficient_evidence":

                stop_reason = "insufficient_evidence"

                logger.warning(
                    "[Orchestrator] Insufficient evidence."
                )

                evidence_gaps.append(
                    decision.get(
                        "reason",
                        "Insufficient evidence to continue investigation."
                    )
                )

                break

            # -------------------------------------------------
            # Validate selected tool
            # -------------------------------------------------

            tool = TOOLS.get(action)

            if tool is None:

                logger.error(
                    f"[Orchestrator] Unknown tool selected: {action}"
                )

                evidence_gaps.append(
                    f"Unknown investigation tool selected: {action}"
                )

                break

            # -------------------------------------------------
            # Notify frontend: selected investigation tool
            # -------------------------------------------------

            if progress_callback:
                progress_callback(
                    action,
                    {
                        "iteration": iteration,
                        "observations": observations,
                        "evidence": evidence,
                        "hypotheses": hypotheses,
                        "tools_used": tools_used,
                        "evidence_gaps": evidence_gaps,
                        "confidence": confidence,
                    },
                )

            # -------------------------------------------------
            # Build investigation context
            # -------------------------------------------------

            context = "\n".join(
                str(item)
                for item in observations[-10:]
            )

            # -------------------------------------------------
            # Execute selected tool
            # -------------------------------------------------

            if action == "get_deployments":

                result = tool(
                    incident=incident,
                    investigation_context=context,
                )

            else:

                result = tool(
                    incident=incident
                )

            # -------------------------------------------------
            # Observability: record tool usage
            # -------------------------------------------------

            record_tool_usage(action)

            tools_used.append(action)

            # -------------------------------------------------
            # Collect evidence
            # -------------------------------------------------

            new_evidence = result.get(
                "evidence",
                []
            )

            if new_evidence:
                evidence.extend(new_evidence)

            # -------------------------------------------------
            # Collect observations
            # -------------------------------------------------

            new_observations = result.get(
                "observations",
                []
            )

            if new_observations:
                observations.extend(
                    new_observations
                )

            # -------------------------------------------------
            # Collect hypotheses
            # -------------------------------------------------

            new_hypotheses = result.get(
                "hypotheses",
                []
            )

            if new_hypotheses:
                hypotheses.extend(
                    new_hypotheses
                )

            # -------------------------------------------------
            # Collect evidence gaps
            # -------------------------------------------------

            new_gaps = result.get(
                "evidence_gaps",
                []
            )

            if new_gaps:
                evidence_gaps.extend(
                    new_gaps
                )

            evidence_gaps = _deduplicate_evidence_gaps(
                evidence_gaps
            )

            # -------------------------------------------------
            # Update confidence
            # -------------------------------------------------

            decision_confidence = decision.get(
                "confidence",
                "low"
            )

            confidence = {
                "high": 0.9,
                "medium": 0.6,
                "low": 0.3,
            }.get(
                decision_confidence,
                0.3
            )

            logger.info(
                f"[Orchestrator] Evidence collected from {action}"
            )

        # -----------------------------------------------------
        # Final Synthesis
        # -----------------------------------------------------

        logger.info(
            "[Orchestrator] Starting final synthesis..."
        )

        # -----------------------------------------------------
        # Notify frontend: final synthesis
        # -----------------------------------------------------

        if progress_callback:
            progress_callback(
                "synthesis",
                {
                    "iteration": iteration if "iteration" in locals() else 0,
                    "observations": observations,
                    "evidence": evidence,
                    "hypotheses": hypotheses,
                    "tools_used": tools_used,
                    "evidence_gaps": evidence_gaps,
                    "confidence": confidence,
                },
            )

        # -----------------------------------------------------
        # Deduplicate accumulated investigation outputs
        # -----------------------------------------------------

        evidence = _deduplicate_items(evidence)
        observations = _deduplicate_items(observations)
        hypotheses = _deduplicate_items(hypotheses)
        evidence_gaps = _deduplicate_items(evidence_gaps)

        # Keep final investigation state focused
        MAX_FINAL_EVIDENCE = 25
        MAX_FINAL_OBSERVATIONS = 20
        MAX_FINAL_HYPOTHESES = 15
        MAX_FINAL_GAPS = 20

        evidence = evidence[-MAX_FINAL_EVIDENCE:]
        observations = observations[-MAX_FINAL_OBSERVATIONS:]
        hypotheses = hypotheses[-MAX_FINAL_HYPOTHESES:]
        evidence_gaps = evidence_gaps[-MAX_FINAL_GAPS:]

        final_result = run_final_synthesis(
            incident=incident,
            observations=observations,
            evidence=evidence,
            hypotheses=hypotheses,
            tools_used=tools_used,
            evidence_gaps=evidence_gaps,
            stop_reason=stop_reason,
        )

        # -----------------------------------------------------
        # Final confidence comes from Final Synthesis
        # -----------------------------------------------------

        root_cause = final_result.get(
            "root_cause",
            {}
        )

        final_confidence = str(
            root_cause.get(
                "confidence",
                "low"
            )
        ).lower()

        confidence = {
            "high": 0.9,
            "medium": 0.6,
            "low": 0.3,
        }.get(
            final_confidence,
            0.3,
        )

        logger.info(
            "[Orchestrator] Investigation complete."
        )

        # -----------------------------------------------------
        # Observability: investigation completed
        # -----------------------------------------------------

        record_investigation_completed(
            stop_reason=stop_reason,
            duration_seconds=time.perf_counter() - start_time,
        )

        # -----------------------------------------------------
        # Final Investigation State
        # -----------------------------------------------------

        return {
            "incident": incident,
            "observations": observations,
            "evidence": evidence,
            "hypotheses": hypotheses,
            "tools_used": tools_used,
            "evidence_gaps": evidence_gaps,
            "confidence": confidence,
            "stop_reason": stop_reason,
            "final_result": final_result,
        }

    except Exception:

        # -----------------------------------------------------
        # Observability: investigation failed
        # -----------------------------------------------------

        record_investigation_failed(
            duration_seconds=time.perf_counter() - start_time,
        )

        logger.exception(
            "[Orchestrator] Investigation failed."
        )

        raise