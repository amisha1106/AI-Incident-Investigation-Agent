"""
IncidentIQ Final Synthesis Agent.

Takes all investigation evidence and produces the final RCA,
probable solution, immediate actions, and prevention plan.
"""

import json
import re

from loguru import logger

from llm import call_gemini


# ---------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------

def _normalize_text(value) -> str:
    """
    Normalize minor whitespace/formatting artifacts in generated
    investigation text.

    This is intentionally conservative:
    - fixes known concatenation artifacts
    - fixes missing spaces around occurrence counters
    - does not rewrite the meaning of evidence
    """
    text = str(value).strip()

    replacements = {
        "connection-managementevidence": "connection-management evidence",
        "connection-poolsaturation": "connection-pool saturation",
        "relationshipbetween": "relationship between",
        "Database errorpattern": "Database error pattern",
        "database errorpattern": "database error pattern",
        "errorpattern": "error pattern",
        "Databaseconnectivity": "Database connectivity",
        "Databaseconnection": "Database connection",
        "nearsaturation": "near saturation",
        "andalerting": "and alerting",
        "andconnection": "and connection",
        "after30s": "after 30s",
        "after60s": "after 60s",
        "after90s": "after 90s",
        "before30s": "before 30s",
        "before60s": "before 60s",
        "before90s": "before 90s",
    }

    for source, target in replacements.items():
        text = text.replace(source, target)

    # Example:
    # "5time(s)" -> "5 time(s)"
    text = re.sub(
        r"(?<=\d)time\(s\)",
        " time(s)",
        text,
    )

    # Example:
    # "3occurrence" -> "3 occurrence"
    text = re.sub(
        r"(?<=\d)occurrence\b",
        " occurrence",
        text,
    )

    return text


def _normalize_text_list(values) -> list[str]:
    """
    Normalize and deduplicate a list of textual investigation items.
    """
    normalized = []

    for value in values or []:
        text = _normalize_text(value)

        if text and text not in normalized:
            normalized.append(text)

    return normalized


def _normalize_result(value):
    if isinstance(value, str):
        return _normalize_text(value)

    if isinstance(value, list):
        return [_normalize_result(item) for item in value]

    if isinstance(value, dict):
        return {
            key: _normalize_result(item)
            for key, item in value.items()
        }

    return value


# ---------------------------------------------------------------------
# Insufficient-evidence result
# ---------------------------------------------------------------------

def _build_insufficient_evidence_result(
    incident: str,
    observations: list,
    evidence: list,
    hypotheses: list,
    tools_used: list,
    evidence_gaps: list,
) -> dict:
    """
    Build a final assessment when the Investigation Agent
    determined that the available evidence is insufficient.

    This function intentionally does not select a root cause.
    """

    gaps = list(evidence_gaps)

    if not gaps:
        gaps.append(
            "The available investigation sources did not provide "
            "enough incident-specific evidence to establish a "
            "probable root cause."
        )

    return {
        "incident_summary": incident,
        "root_cause": {
            "summary": (
                "No reliable root cause could be established "
                "from the available evidence."
            ),
            "explanation": (
                "The investigation explored the available "
                "investigation sources, but the collected evidence "
                "could not be sufficiently aligned with the incident "
                "to support a reliable root-cause assessment."
            ),
            "confidence": "low",
        },
        "supporting_evidence": evidence,
        "alternative_hypotheses": [
            {
                "hypothesis": str(hypothesis),
                "reason": (
                    "This remains a hypothesis because the available "
                    "evidence does not establish that it caused the incident."
                ),
            }
            for hypothesis in hypotheses[-5:]
        ],
        "probable_solution": [
            "Collect additional incident-specific telemetry.",
            "Identify the affected component or dependency.",
            "Use the additional evidence to distinguish between competing hypotheses.",
        ],
        "immediate_actions": [
            "Continue monitoring the affected service.",
            "Collect application, dependency, and infrastructure telemetry.",
            "Avoid making irreversible remediation decisions based only on the current evidence.",
        ],
        "long_term_prevention": [
            "Improve observability coverage across application and downstream dependencies.",
            "Ensure incidents contain enough component and symptom context for investigation.",
        ],
        "evidence_gaps": gaps,
        "severity": "medium",
    }


# ---------------------------------------------------------------------
# Deterministic fallback result
# ---------------------------------------------------------------------

def _build_fallback_result(
    incident: str,
    observations: list,
    evidence: list,
    hypotheses: list,
    tools_used: list,
    evidence_gaps: list,
) -> dict:
    """
    Build a deterministic RCA when Gemini is unavailable.

    This fallback uses only the evidence collected by the
    investigation tools and does not invent new telemetry.
    """

    evidence_text = " ".join(
        str(item).lower()
        for item in evidence
    )

    # ---------------------------------------------------------
    # Identify the strongest evidence pattern
    # ---------------------------------------------------------

    db_pool_issue = (
        "connection pool" in evidence_text
        or "db pool" in evidence_text
        or "databaseconnectionleakerror" in evidence_text
        or "pool exhausted" in evidence_text
    )

    deployment_issue = (
        "deployment v3.8" in evidence_text
        or "payment retry logic" in evidence_text
        or "new db pool config" in evidence_text
    )

    latency_issue = (
        "latency" in evidence_text
        or "p99" in evidence_text
    )

    error_issue = (
        "error rate" in evidence_text
        or "error" in evidence_text
    )

    # ---------------------------------------------------------
    # Root-cause assessment
    # ---------------------------------------------------------

    if db_pool_issue and deployment_issue:

        root_cause_summary = (
            "The latest deployment is the most probable contributor "
            "to database connection pool saturation and checkout "
            "latency degradation."
        )

        root_cause_explanation = (
            "The collected evidence shows database connection-related "
            "errors, connection-pool exhaustion, database pool "
            "utilization reaching 100%, and a recent deployment that "
            "introduced a new DB pool configuration and payment retry "
            "logic. These signals are temporally and technically "
            "consistent with the incident, but the available evidence "
            "does not prove causality."
        )

        root_cause_confidence = "medium"

        supporting_evidence = [
            item
            for item in evidence
            if (
                "pool" in str(item).lower()
                or "databaseconnection" in str(item).lower()
                or "deployment v3.8" in str(item).lower()
                or "payment retry" in str(item).lower()
            )
        ]

        probable_solution = [
            "Review the DB connection pool configuration introduced "
            "in the latest deployment.",
            "Review the payment retry logic for excessive or repeated "
            "database connection usage.",
            "Validate connection acquisition and release behavior "
            "before increasing pool capacity.",
        ]

        immediate_actions = [
            "Consider rolling back the latest deployment if the "
            "incident is actively impacting users.",
            "Monitor database connection-pool utilization and "
            "checkout latency during mitigation.",
            "Inspect active database connections for leaks or "
            "unexpected retry amplification.",
        ]

        long_term_prevention = [
            "Add monitoring and alerting for database connection-pool "
            "saturation.",
            "Add deployment validation for DB pool configuration changes.",
            "Add regression tests for retry behavior and connection "
            "cleanup.",
            "Correlate deployment changes with latency and error-rate "
            "changes in observability dashboards.",
        ]

    elif db_pool_issue:

        root_cause_summary = (
            "Database connection-pool saturation is the strongest "
            "observed contributor to the incident."
        )

        root_cause_explanation = (
            "The investigation found database connection-related "
            "errors and connection-pool saturation. However, the "
            "available evidence does not establish the underlying "
            "cause of the saturation."
        )

        root_cause_confidence = "medium"

        supporting_evidence = [
            item
            for item in evidence
            if (
                "pool" in str(item).lower()
                or "databaseconnection" in str(item).lower()
            )
        ]

        probable_solution = [
            "Investigate database connection acquisition and release.",
            "Review connection-pool configuration and usage patterns.",
        ]

        immediate_actions = [
            "Monitor database connection-pool utilization.",
            "Investigate active and leaked database connections.",
        ]

        long_term_prevention = [
            "Add database connection-pool saturation monitoring.",
            "Add connection lifecycle and leak detection.",
        ]

    elif latency_issue and error_issue:

        root_cause_summary = (
            "The incident is associated with simultaneous latency "
            "and error-rate degradation, but the available evidence "
            "is insufficient to identify a specific root cause."
        )

        root_cause_explanation = (
            "Metrics show elevated latency and error rates, but the "
            "available evidence does not establish which dependency "
            "or component caused the degradation."
        )

        root_cause_confidence = "low"

        supporting_evidence = evidence

        probable_solution = [
            "Investigate the application and downstream dependencies "
            "responsible for the latency and errors.",
        ]

        immediate_actions = [
            "Monitor latency and error-rate trends.",
            "Inspect application traces and downstream dependency health.",
        ]

        long_term_prevention = [
            "Improve distributed tracing and dependency-level monitoring.",
            "Create alerts for correlated latency and error-rate spikes.",
        ]

    else:

        root_cause_summary = (
            "Insufficient evidence to determine a specific root cause."
        )

        root_cause_explanation = (
            "The investigation collected evidence, but the available "
            "signals do not provide enough information to establish "
            "a probable root cause with confidence."
        )

        root_cause_confidence = "low"

        supporting_evidence = evidence

        probable_solution = [
            "Collect additional application, infrastructure, and "
            "dependency-level evidence.",
        ]

        immediate_actions = [
            "Continue monitoring the affected service.",
            "Collect additional telemetry before making a causal decision.",
        ]

        long_term_prevention = [
            "Improve observability coverage across application and "
            "downstream dependencies.",
        ]

    # ---------------------------------------------------------
    # Alternative hypotheses
    # ---------------------------------------------------------

    alternative_hypotheses = []

    if deployment_issue:
        alternative_hypotheses.append(
            {
                "hypothesis": (
                    "The payment retry logic introduced by the latest "
                    "deployment may be contributing to resource pressure."
                ),
                "reason": (
                    "The deployment introduced payment retry logic, but "
                    "the available evidence does not directly measure "
                    "retry frequency or its database impact."
                ),
            }
        )

    alternative_hypotheses.append(
        {
            "hypothesis": (
                "An underlying database performance or dependency issue "
                "may be contributing to the observed degradation."
            ),
            "reason": (
                "Database-level query execution and distributed tracing "
                "evidence are not available."
            ),
        }
    )

    # ---------------------------------------------------------
    # Severity
    # ---------------------------------------------------------

    if (
        "100%" in evidence_text
        or "7997" in evidence_text
        or "11.29%" in evidence_text
    ):
        severity = "high"
    elif latency_issue or error_issue:
        severity = "medium"
    else:
        severity = "low"

    return {
        "incident_summary": incident,
        "root_cause": {
            "summary": root_cause_summary,
            "explanation": root_cause_explanation,
            "confidence": root_cause_confidence,
        },
        "supporting_evidence": supporting_evidence,
        "alternative_hypotheses": alternative_hypotheses,
        "probable_solution": probable_solution,
        "immediate_actions": immediate_actions,
        "long_term_prevention": long_term_prevention,
        "evidence_gaps": evidence_gaps + [
            "LLM-based final synthesis was unavailable.",
        ],
        "severity": severity,
    }


# ---------------------------------------------------------------------
# Main final synthesis
# ---------------------------------------------------------------------

def run_final_synthesis(
    incident: str,
    observations: list,
    evidence: list,
    hypotheses: list,
    tools_used: list,
    evidence_gaps: list,
    stop_reason: str = "max_iterations_reached",
) -> dict:
    """
    Synthesize the investigation evidence into a final result.

    If the investigation explicitly ended because evidence was
    insufficient, do not generate a root-cause claim.
    """

    logger.info(
        "[FinalSynthesis] Building final incident assessment..."
    )

    # ---------------------------------------------------------
    # Normalize incoming investigation data
    # ---------------------------------------------------------

    incident = _normalize_text(incident)

    observations = _normalize_text_list(observations)
    evidence = _normalize_text_list(evidence)
    hypotheses = _normalize_text_list(hypotheses)
    tools_used = _normalize_text_list(tools_used)
    evidence_gaps = _normalize_text_list(evidence_gaps)

    # ---------------------------------------------------------
    # Explicit insufficient-evidence path
    # ---------------------------------------------------------

    if stop_reason == "insufficient_evidence":

        logger.warning(
            "[FinalSynthesis] Investigation ended with "
            "insufficient evidence. Skipping RCA generation."
        )

        gaps = list(evidence_gaps)

        if not gaps:
            gaps.append(
                "The available investigation sources did not provide "
                "enough incident-specific evidence to establish a "
                "probable root cause."
            )

        result = {
            "incident_summary": incident,
            "root_cause": {
                "summary": (
                    "No reliable root cause could be established "
                    "from the available evidence."
                ),
                "explanation": (
                    "The Investigation Agent explored the available "
                    "investigation sources, but the collected evidence "
                    "could not be sufficiently aligned with the incident "
                    "to support a reliable root-cause assessment."
                ),
                "confidence": "low",
            },
            "supporting_evidence": evidence,
            "alternative_hypotheses": [
                {
                    "hypothesis": str(hypothesis),
                    "reason": (
                        "This remains a hypothesis because the available "
                        "evidence does not establish that it caused the incident."
                    ),
                }
                for hypothesis in hypotheses[-5:]
            ],
            "probable_solution": [
                "Collect additional incident-specific telemetry.",
                "Identify the affected component or dependency.",
                "Use the additional evidence to distinguish between competing hypotheses.",
            ],
            "immediate_actions": [
                "Continue monitoring the affected service.",
                "Collect application, dependency, and infrastructure telemetry.",
                "Avoid making irreversible remediation decisions based only on the current evidence.",
            ],
            "long_term_prevention": [
                "Improve observability coverage across application and downstream dependencies.",
                "Ensure incidents contain enough component and symptom context for investigation.",
            ],
            "evidence_gaps": gaps,
            "severity": "medium",
        }

        return _normalize_result(result)

    # ---------------------------------------------------------
    # Normal Gemini synthesis
    # ---------------------------------------------------------

    prompt = f"""
You are the final RCA reasoning component of IncidentIQ.

Your job is to synthesize the evidence collected during
an investigation and produce a cautious, evidence-based
incident assessment.

INCIDENT:

{incident}

TOOLS USED:

{json.dumps(tools_used, indent=2)}

INVESTIGATION STOP REASON:

{stop_reason}

OBSERVATIONS:

{json.dumps(observations, indent=2, default=str)}

EVIDENCE:

{json.dumps(evidence, indent=2, default=str)}

HYPOTHESES:

{json.dumps(hypotheses, indent=2, default=str)}

EVIDENCE GAPS:

{json.dumps(evidence_gaps, indent=2, default=str)}

IMPORTANT RULES:

1. Do not claim causality unless the evidence supports it.
2. Clearly distinguish confirmed observations from hypotheses.
3. Identify the most probable root cause.
4. Explain the evidence supporting that conclusion.
5. Mention important alternative hypotheses.
6. If evidence is insufficient, explicitly say so.
7. Do not invent metrics, logs, deployments, or events.
8. Base the solution on the evidence available.

Return ONLY valid JSON.

Return this structure:

{{
  "incident_summary": "short summary of the incident",

  "root_cause": {{
    "summary": "most probable root cause",
    "explanation": "why this is the most probable explanation",
    "confidence": "high|medium|low"
  }},

  "supporting_evidence": [
    "evidence supporting the root cause"
  ],

  "alternative_hypotheses": [
    {{
      "hypothesis": "alternative explanation",
      "reason": "why it remains possible"
    }}
  ],

  "probable_solution": [
    "most appropriate solution based on the evidence"
  ],

  "immediate_actions": [
    "action to reduce or stop the incident"
  ],

  "long_term_prevention": [
    "engineering change that could prevent recurrence"
  ],

  "evidence_gaps": [
    "important information still missing"
  ],

  "severity": "critical|high|medium|low"
}}
"""

    # ---------------------------------------------------------
    # Gemini synthesis + deterministic fallback
    # ---------------------------------------------------------

    try:

        response = call_gemini(prompt)

        text = re.sub(
            r"(?<=\d)time\(s\)",
            " time(s)",
            text,
        )

        text = re.sub(
            r"(?<=\d)occurrence\b",
            " occurrence",
            text,
        )

        text = re.sub(
            r"\bat(?=\d{4}-\d{2}-\d{2}T)",
            "at ",
            text,
        )

        text = re.sub(
            r"\boccurred(?=\d+\s*time)",
            "occurred ",
            text,
        )

        text = re.sub(
            r"```(?:json)?\s*",
            "",
            response,
        )

        text = re.sub(
            r"```\s*$",
            "",
            text,
        )

        result = json.loads(
            text.strip()
        )

        # -----------------------------------------------------
        # Confidence calibration
        # -----------------------------------------------------

        gap_text = " ".join(
            str(gap).lower()
            for gap in evidence_gaps
        )

        causal_gap_terms = [
            "cannot establish causality",
            "cannot establish the root cause",
            "does not establish causality",
            "exact deployment-to-incident timing",
            "actual code changes",
            "distributed tracing",
            "direct database connection inspection",
            "query execution",
            "lock/wait",
        ]

        causal_gaps_present = sum(
            1
            for term in causal_gap_terms
            if term in gap_text
        )

        if (
            isinstance(result, dict)
            and isinstance(result.get("root_cause"), dict)
        ):
            current_confidence = str(
                result["root_cause"].get(
                    "confidence",
                    "low",
                )
            ).lower()

            if (
                current_confidence == "high"
                and causal_gaps_present >= 1
            ):
                result["root_cause"]["confidence"] = "medium"

    except Exception as e:

        logger.warning(
            "[FinalSynthesis] Gemini unavailable or returned "
            f"invalid response: {e}"
        )

        result = _build_fallback_result(
            incident=incident,
            observations=observations,
            evidence=evidence,
            hypotheses=hypotheses,
            tools_used=tools_used,
            evidence_gaps=evidence_gaps,
        )

    # ---------------------------------------------------------
    # Final output normalization
    #
    # This runs for BOTH:
    # - Gemini-generated results
    # - deterministic fallback results
    #
    # Therefore formatting artifacts cannot leak through the API.
    # ---------------------------------------------------------

    result = _normalize_result(result)

    logger.info(
        "[FinalSynthesis] Final assessment generated."
    )

    return result