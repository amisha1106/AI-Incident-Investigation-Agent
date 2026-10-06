"""
IncidentIQ Investigation Agent.

Responsible for deciding what should be investigated next.
It does not directly investigate the incident.
"""

import json
import re

from loguru import logger

from llm import call_gemini

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
AVAILABLE_TOOLS = [
    "query_logs",
    "query_metrics",
    "get_deployments",
    "inspect_api",
    "inspect_database",
    "inspect_infrastructure",
    "inspect_security",
    "search_historical_incidents",
    "search_recent_commits",
]

def _is_incident_evidence_aligned(
    incident: str,
    evidence: list,
    hypotheses: list,
    observations: list,
) -> bool:
    """
    Determine whether the collected evidence is sufficiently
    connected to the incident being investigated.

    Strong evidence from the dataset should not automatically
    become the root cause when the incident itself is too vague.
    """

    incident_text = str(incident).lower()

    evidence_text = " ".join(
        str(item)
        for item in evidence
    ).lower()

    observation_text = " ".join(
        str(item)
        for item in observations
    ).lower()

    hypothesis_text = " ".join(
        str(item)
        for item in hypotheses
    ).lower()

    state_text = " ".join(
        [
            evidence_text,
            observation_text,
            hypothesis_text,
        ]
    )



    # ---------------------------------------------------------
    # Generic incident descriptions
    # ---------------------------------------------------------

    generic_patterns = [
        "service is behaving unexpectedly",
        "service is behaving abnormally",
        "something is wrong with the service",
        "what is causing the issue",
        "underlying cause is unknown",
        "affected component is unknown",
        "unknown cause",
        "unexpected behavior",
        "unexpected behaviour",
    ]

    generic_incident = any(
        pattern in incident_text
        for pattern in generic_patterns
    )

    # ---------------------------------------------------------
    # Concrete incident signals
    # ---------------------------------------------------------

    concrete_terms = [
        "failure",
        "failures",
        "failed",
        "error",
        "errors",
        "latency",
        "slow",
        "timeout",
        "timeouts",
        "degradation",
        "unavailable",
        "connection",
        "database",
        "db",
        "api",
        "endpoint",
        "request",
        "deployment",
        "deploy",
        "release",
        "infrastructure",
        "cpu",
        "memory",
        "disk",
        "resource exhaustion",
    ]

    has_concrete_signal = any(
        term in incident_text
        for term in concrete_terms
    )

    # ---------------------------------------------------------
    # Concrete system/component context
    # ---------------------------------------------------------

    component_terms = [
        "api",
        "endpoint",
        "checkout",
        "payment",
        "database",
        "db",
        "connection pool",
        "deployment",
        "release",
        "infrastructure",
        "cpu",
        "memory",
        "disk",
        "host",
        "node",
        "container",
    ]

    has_component_context = any(
        term in incident_text
        for term in component_terms
    )

    # ---------------------------------------------------------
    # Completely generic incident
    # ---------------------------------------------------------

    if generic_incident and not has_component_context:
        return False

    # ---------------------------------------------------------
    # Symptom-only incident
    #
    # Example:
    # "Users are reporting intermittent failures."
    #
    # This tells us there is a symptom, but not which part
    # of the system is affected.
    # ---------------------------------------------------------

    if has_concrete_signal and not has_component_context:

        investigation_domains = [
            "api",
            "endpoint",
            "database",
            "connection",
            "pool",
            "deployment",
            "infrastructure",
            "cpu",
            "memory",
            "disk",
            "host",
            "node",
            "container",
        ]

        has_supported_domain = any(
            term in state_text
            for term in investigation_domains
        )

        # Evidence may be strong, but it still cannot establish
        # that this domain is actually responsible for the
        # incident when the incident gives no component context.
        if not has_supported_domain:
            return False

        return False

    # ---------------------------------------------------------
    # Explicit domain in incident
    #
    # If the incident explicitly mentions a database, API,
    # deployment, or infrastructure problem, evidence should
    # contain corresponding signals.
    # ---------------------------------------------------------

    domain_terms = {
        "database": [
            "database",
            "db",
            "connection",
            "connection pool",
            "pool",
        ],
        "api": [
            "api",
            "endpoint",
            "http",
            "request",
        ],
        "deployment": [
            "deployment",
            "deploy",
            "release",
            "version",
        ],
        "infrastructure": [
            "infrastructure",
            "cpu",
            "memory",
            "disk",
            "host",
            "node",
            "container",
            "resource exhaustion",
        ],
    }

    for domain, terms in domain_terms.items():

        if any(
            term in incident_text
            for term in terms
        ):

            if not any(
                term in state_text
                for term in terms
            ):
                return False

    return True


def _assess_fallback_sufficiency(
    incident: str,
    observations: list,
    evidence: list,
    hypotheses: list,
    unused_tools: list,
    evidence_gaps: list,
    tools_used: list,
) -> dict | None:
    """
    Decide whether the current evidence is strong enough to stop
    when Gemini is unavailable.

    The fallback is intentionally conservative. It requires:
    - enough evidence,
    - at least one hypothesis,
    - evidence from multiple signal types,
    - no unresolved gap directly related to the current hypotheses.
    """

    if not evidence or not hypotheses:
        return None

    if not _is_incident_evidence_aligned(
    incident=incident,
    evidence=evidence,
    hypotheses=hypotheses,
    observations=observations,
    ):
        return None

    # ---------------------------------------------------------
    # Explicit uncertainty must prevent premature fallback finish.
    # ---------------------------------------------------------
    incident_text = str(incident).lower()

    uncertainty_terms = [
        "unclear",
        "unknown",
        "not confirmed",
        "no confirmed",
        "underlying cause",
        "affected component",
        "cause is unclear",
    ]

    explicit_uncertainty = any(
        term in incident_text
        for term in uncertainty_terms
    )

    if explicit_uncertainty:
        return None

    # Do not allow the fallback to finish after only one
    # investigation source.
    if len(set(tools_used)) < 2:
        return None

    # Do not stop after only one or two pieces of evidence.
    if len(evidence) < 3:
        return None

    state_text = " ".join(
        [
            str(incident),
            *[str(item) for item in observations[-15:]],
            *[str(item) for item in evidence[-20:]],
            *[str(item) for item in hypotheses[-10:]],
        ]
    ).lower()

    # ---------------------------------------------------------
    # Check whether evidence comes from multiple signal types.
    # ---------------------------------------------------------

    signal_families = {
        "application": any(
            term in state_text
            for term in [
                "error",
                "exception",
                "failed",
                "failure",
            ]
        ),
        "performance": any(
            term in state_text
            for term in [
                "latency",
                "p99",
                "error rate",
                "spike",
            ]
        ),
        "database": any(
            term in state_text
            for term in [
                "database",
                "connection pool",
                "pool exhausted",
                "connection refused",
            ]
        ),
        "deployment": any(
            term in state_text
            for term in [
                "deployment",
                "release",
                "rollback",
                "version",
            ]
        ),
        "api": any(
            term in state_text
            for term in [
                "api",
                "endpoint",
                "http",
                "request",
            ]
        ),
    }

    # We want at least two independent evidence categories.
    if sum(signal_families.values()) < 2:
        return None

    # ---------------------------------------------------------
    # Check whether an important evidence gap is still relevant
    # to one of the current hypotheses.
    # ---------------------------------------------------------

    gap_text = " ".join(
        str(item).lower()
        for item in evidence_gaps[-15:]
    )

    critical_gap_terms = {
        "database": [
            "database",
            "connection",
            "pool",
        ],
        "api": [
            "api",
            "endpoint",
            "http",
            "timeout",
        ],
        "deployment": [
            "deployment",
            "release",
            "code change",
            "version",
        ],
        "infrastructure": [
            "cpu",
            "memory",
            "disk",
            "host",
            "node",
            "container",
        ],
    }

    relevant_gap_tools = set()

    for hypothesis in hypotheses[-5:]:
        hypothesis_text = str(hypothesis).lower()

        for tool_name, terms in {
            "inspect_database": [
                "database",
                "connection",
                "connection pool",
                "pool",
            ],
            "inspect_api": [
                "api",
                "endpoint",
                "http",
                "timeout",
            ],
            "get_deployments": [
                "deployment",
                "release",
                "code change",
                "version",
            ],
            "inspect_infrastructure": [
                "cpu",
                "memory",
                "disk",
                "host",
                "node",
                "container",
            ],
        }.items():

            hypothesis_matches = any(
                term in hypothesis_text
                for term in terms
            )

            gap_matches = any(
                term in gap_text
                for term in terms
            )

            if hypothesis_matches and gap_matches:
                relevant_gap_tools.add(tool_name)

    # Continue only when an unused tool can actually investigate
    # the unresolved hypothesis-specific gap.
    if relevant_gap_tools.intersection(unused_tools):
        return None

    # ---------------------------------------------------------
    # Explicit incident domains must be investigated first.
    # ---------------------------------------------------------

    required_domain_tools = {
        "database": (
            "inspect_database",
            ["database", "connection pool", "db"],
        ),
        "api": (
            "inspect_api",
            ["api", "endpoint"],
        ),
        "deployment": (
            "get_deployments",
            ["deployment", "deploy", "release", "version"],
        ),
        "infrastructure": (
            "inspect_infrastructure",
            [
                "infrastructure",
                "cpu",
                "memory",
                "disk",
                "host",
                "node",
                "container",
            ],
        ),
        "security": (
            "inspect_security",
            [
                "security",
                "authentication",
                "authorization",
                "unauthorized",
                "forbidden",
            ],
        ),
        "historical": (
            "search_historical_incidents",
            [
                "historical incident",
                "similar incident",
                "previous incident",
                "past incident",
                "happened before",
            ],
        ),
    }

    for required_tool, terms in required_domain_tools.values():

        if any(term in incident_text for term in terms):

            if required_tool in unused_tools:
                return None

    # ---------------------------------------------------------
    # Evidence is sufficient.
    # ---------------------------------------------------------

    return {
        "next_action": "finish",
        "reason": (
            "Gemini was unavailable, but the investigation has "
            "collected multiple supporting signals across independent "
            "evidence types and no hypothesis-specific unresolved "
            "evidence gap remains."
        ),
        "investigation_question": (
            "Is the collected evidence sufficient to produce "
            "the final assessment?"
        ),
        "confidence": "medium",
    }


def _finish_decision_is_supported(
    incident: str,
    evidence: list,
    hypotheses: list,
    observations: list,
    unused_tools: list,
    tools_used: list,
) -> bool:
    """
    Validate whether the Investigation Agent is allowed to finish.

    A finish is allowed only when:
    - evidence exists,
    - hypotheses exist,
    - evidence is aligned with the incident,
    - multiple investigation sources were used,
    - multiple signal families are present,
    - explicitly mentioned domains were investigated,
    - and no unused tool can directly resolve an important
      hypothesis-specific evidence gap.
    """

    if not evidence or not hypotheses:
        return False

    if not _is_incident_evidence_aligned(
        incident=incident,
        evidence=evidence,
        hypotheses=hypotheses,
        observations=observations,
    ):
        return False

    incident_text = str(incident).lower()

    # ---------------------------------------------------------
    # Explicit uncertainty
    # ---------------------------------------------------------

    uncertainty_terms = [
        "unclear",
        "unknown",
        "not confirmed",
        "no confirmed",
        "underlying cause",
        "affected component",
        "what is causing",
        "cause is unclear",
    ]

    explicit_uncertainty = any(
        term in incident_text
        for term in uncertainty_terms
    )

    if explicit_uncertainty:
        component_terms = [
            "database",
            "db",
            "api",
            "endpoint",
            "service",
            "deployment",
            "infrastructure",
            "server",
            "host",
            "container",
            "authentication",
            "security",
            "network",
            "gateway",
        ]

        if not any(
            term in incident_text
            for term in component_terms
        ):
            return False

        if len(set(tools_used)) < 3:
            return False

    # ---------------------------------------------------------
    # Basic investigation depth
    # ---------------------------------------------------------

    if len(set(tools_used)) < 2:
        return False

    if len(evidence) < 3:
        return False

    # ---------------------------------------------------------
    # Multiple independent signal families
    # ---------------------------------------------------------

    state_text = " ".join(
        [
            str(incident),
            *[str(item) for item in observations[-15:]],
            *[str(item) for item in evidence[-30:]],
            *[str(item) for item in hypotheses[-10:]],
        ]
    ).lower()

    signal_families = 0

    if any(
        term in state_text
        for term in [
            "error",
            "exception",
            "failed",
            "failure",
        ]
    ):
        signal_families += 1

    if any(
        term in state_text
        for term in [
            "latency",
            "p99",
            "error rate",
            "spike",
        ]
    ):
        signal_families += 1

    if any(
        term in state_text
        for term in [
            "database",
            "connection pool",
            "pool exhausted",
            "connection refused",
        ]
    ):
        signal_families += 1

    if any(
        term in state_text
        for term in [
            "deployment",
            "release",
            "version",
            "rollback",
        ]
    ):
        signal_families += 1

    if any(
        term in state_text
        for term in [
            "api",
            "endpoint",
            "http",
            "request",
            "timeout",
        ]
    ):
        signal_families += 1

    if signal_families < 2:
        return False

    # ---------------------------------------------------------
    # Explicit incident domains MUST be investigated
    # ---------------------------------------------------------

    required_domain_tools = {
        "database": (
            "inspect_database",
            [
                "database",
                "connection pool",
                "db",
            ],
        ),

        "api": (
            "inspect_api",
            [
                "api",
                "endpoint",
            ],
        ),

        "deployment": (
            "get_deployments",
            [
                "deployment",
                "deploy",
                "release",
                "version",
            ],
        ),

        "infrastructure": (
            "inspect_infrastructure",
            [
                "infrastructure",
                "cpu",
                "memory",
                "disk",
                "host",
                "node",
                "container",
            ],
        ),

        "security": (
            "inspect_security",
            [
                "security",
                "authentication",
                "authorization",
                "unauthorized",
                "forbidden",
            ],
        ),

        "historical": (
            "search_historical_incidents",
            [
                "historical incident",
                "similar incident",
                "previous incident",
                "past incident",
                "happened before",
            ],
        ),
    }

    for required_tool, terms in required_domain_tools.values():

        if any(term in incident_text for term in terms):

            if required_tool in unused_tools:
                return False

    # ---------------------------------------------------------
    # Hypothesis-specific unresolved gaps
    # ---------------------------------------------------------

    gap_text = " ".join(
        str(item).lower()
        for item in evidence_gaps
    )

    hypothesis_text = " ".join(
        str(item).lower()
        for item in hypotheses[-5:]
    )

    unresolved_tools = {
        "inspect_database": [
            "database",
            "connection",
            "pool",
        ],
        "inspect_api": [
            "api",
            "endpoint",
            "timeout",
            "http",
        ],
        "get_deployments": [
            "deployment",
            "release",
            "code change",
            "version",
        ],
        "inspect_infrastructure": [
            "cpu",
            "memory",
            "disk",
            "host",
            "node",
            "container",
        ],
    }

    for tool_name, terms in unresolved_tools.items():

        if tool_name not in unused_tools:
            continue

        hypothesis_relevant = any(
            term in hypothesis_text
            for term in terms
        )

        gap_relevant = any(
            term in gap_text
            for term in terms
        )

        if hypothesis_relevant and gap_relevant:
            return False

    return True


def _select_fallback_tool(
    incident: str,
    observations: list,
    evidence: list,
    hypotheses: list,
    unused_tools: list,
    evidence_gaps: list,
    tools_used: list,
) -> dict:
    """
    Select the most relevant unused tool when Gemini is unavailable.

    This is a deterministic evidence-driven fallback.
    It does not simply follow the order of AVAILABLE_TOOLS.
    """

    # ---------------------------------------------------------
    # Build a single searchable representation of the state
    # ---------------------------------------------------------

    state_text = " ".join(
        [
            str(incident),
            *[str(item) for item in observations[-15:]],
            *[str(item) for item in evidence[-20:]],
            *[str(item) for item in hypotheses[-10:]],
            *[str(item) for item in evidence_gaps[-15:]],
        ]
    ).lower()

    # ---------------------------------------------------------
    # Separate actual incident/evidence signals from telemetry
    # gaps. Missing telemetry should not create a new reason
    # to investigate that same unavailable domain.
    # ---------------------------------------------------------

    signal_text = " ".join(
        [
            str(incident),
            *[str(item) for item in observations[-15:]],
            *[str(item) for item in evidence[-20:]],
            *[str(item) for item in hypotheses[-10:]],
        ]
    ).lower()

    code_change_keywords = [
        "code change",
        "code changes",
        "recent change",
        "recent changes",
        "recent commit",
        "recent commits",
        "commit",
        "commits",
        "regression",
        "bug introduced",
        "new feature",
        "configuration change",
        "config change",
        "after a code change",
    ]

    if (
        "search_recent_commits" in unused_tools
        and any(
            keyword in signal_text
            for keyword in code_change_keywords
        )
    ):
        return {
            "next_action": "search_recent_commits",
            "reason": (
                "The incident or investigation state indicates a "
                "potential recent code or configuration change."
            ),
            "investigation_question": (
                "Are recent GitHub commits temporally or technically "
                "relevant to the incident?"
            ),
            "confidence": "medium",
        }

    # ---------------------------------------------------------
    # Score each unused tool based on the evidence currently
    # available.
    # ---------------------------------------------------------

    tool_scores = {
        tool: 0
        for tool in unused_tools
    }

    tool_reasons = {}

    def add_score(tool: str, score: int, reason: str):
        if tool in tool_scores:
            tool_scores[tool] += score
            tool_reasons.setdefault(tool, []).append(reason)

    # ---------------------------------------------------------
    # LOG INVESTIGATION
    # ---------------------------------------------------------

    log_keywords = [
        "log",
        "error",
        "exception",
        "warning",
        "stack trace",
        "failed",
        "failure",
    ]

    log_score = sum(
        1 for keyword in log_keywords
        if keyword in state_text
    )

    if log_score:
        add_score(
            "query_logs",
            log_score,
            "Application error/log evidence may provide additional context.",
        )

    # ---------------------------------------------------------
    # METRICS INVESTIGATION
    # ---------------------------------------------------------

    metric_keywords = [
        "latency",
        "p99",
        "error rate",
        "metric",
        "spike",
        "anomaly",
        "throughput",
        "request volume",
    ]

    metric_score = sum(
        1 for keyword in metric_keywords
        if keyword in state_text
    )

    if metric_score:
        add_score(
            "query_metrics",
            metric_score,
            "Service-level metric behaviour is relevant to the incident.",
        )

    # ---------------------------------------------------------
    # DEPLOYMENT INVESTIGATION
    # ---------------------------------------------------------

    deployment_keywords = [
        "deployment",
        "deploy",
        "release",
        "version",
        "config change",
        "configuration change",
        "rollback",
        "recent change",
        "changed",
    ]

    deployment_score = sum(
        1 for keyword in deployment_keywords
        if keyword in state_text
    )

    if deployment_score:
        add_score(
            "get_deployments",
            deployment_score,
            "A deployment or configuration change may explain the incident.",
        )

    # ---------------------------------------------------------
    # API INVESTIGATION
    # ---------------------------------------------------------

    api_keywords = [
        "api",
        "endpoint",
        "http",
        "request",
        "timeout",
        "status code",
        "rate limit",
        "gateway",
        "response time",
    ]

    api_score = sum(
        1 for keyword in api_keywords
        if keyword in state_text
    )

    if api_score:
        add_score(
            "inspect_api",
            api_score,
            "API/service behaviour is relevant to the incident.",
        )

    # ---------------------------------------------------------
    # DATABASE INVESTIGATION
    # ---------------------------------------------------------

    database_keywords = [
        "database",
        "db",
        "sql",
        "query",
        "connection",
        "connection pool",
        "pool",
        "pool exhausted",
        "connection refused",
        "databaseconnection",
        "retry limit",
        "lock",
        "transaction",
    ]

    database_score = sum(
        1 for keyword in database_keywords
        if keyword in state_text
    )

    if database_score:
        add_score(
            "inspect_database",
            database_score,
            "Database or connection-management evidence is present.",
        )

    # ---------------------------------------------------------
    # INFRASTRUCTURE INVESTIGATION
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # INFRASTRUCTURE INVESTIGATION
    # ---------------------------------------------------------

    infrastructure_keywords = [
        "infrastructure",
        "cpu",
        "memory",
        "ram",
        "disk",
        "host",
        "node",
        "container",
        "filesystem",
        "resource saturation",
    ]

    infrastructure_score = sum(
        1 for keyword in infrastructure_keywords
        if keyword in signal_text
    )

    # Only investigate infrastructure when the incident/state
    # contains an explicit infrastructure signal. Generic words
    # such as "request", "timeout", or "error" are not sufficient.
    explicit_infrastructure_signal = any(
        keyword in signal_text
        for keyword in [
            "cpu",
            "memory",
            "ram",
            "disk",
            "host",
            "node",
            "container",
            "filesystem",
            "infrastructure",
            "resource saturation",
        ]
    )

    if infrastructure_score and explicit_infrastructure_signal:
        add_score(
            "inspect_infrastructure",
            infrastructure_score,
            "Explicit infrastructure/resource evidence is relevant.",
        )


    # ---------------------------------------------------------
    # SECURITY INVESTIGATION
    # ---------------------------------------------------------

    security_keywords = [
        "security",
        "authentication",
        "authorization",
        "unauthorized",
        "forbidden",
        "permission",
        "credential",
        "token",
        "login",
        "attack",
        "suspicious",
        "blocked",
        "rate limit",
    ]

    security_score = sum(
        1 for keyword in security_keywords
        if keyword in state_text
    )

    if security_score:
        add_score(
            "inspect_security",
            security_score,
            "Security-related evidence may be relevant to the incident.",
        )

    historical_keywords = [
    "similar incident",
    "previous incident",
    "past incident",
    "historical incident",
    "similar issue",
    "previous issue",
    "past issue",
    "has this happened before",
    "happened before",
    "historically",
    "known issue",
    "known incident",
]

    historical_score = sum(
        1 for keyword in historical_keywords
        if keyword in state_text
    )

    if historical_score:
        add_score(
            "search_historical_incidents",
            historical_score,
            "Historical incidents may provide useful supporting context.",
        )

    # ---------------------------------------------------------
    # Explicit evidence-gap signals
    # should receive stronger weight.
    # ---------------------------------------------------------

    gap_text = " ".join(
        str(item).lower()
        for item in evidence_gaps[-15:]
    )

    if "database" in gap_text or "connection" in gap_text:
        add_score(
            "inspect_database",
            5,
            "An unresolved database/connection evidence gap exists.",
        )

    if (
        "http" in gap_text
        or "endpoint" in gap_text
        or "api gateway" in gap_text
        or "timeout" in gap_text
    ):
        add_score(
            "inspect_api",
            5,
            "An unresolved API evidence gap exists.",
        )

    if (
        "deployment" in gap_text
        or "code change" in gap_text
        or "causality" in gap_text
    ):
        add_score(
            "get_deployments",
            4,
            "Deployment/change evidence remains unresolved.",
        )


    # ---------------------------------------------------------
    # If there is a strong database signal, database inspection
    # should be preferred over unrelated tools.
    # ---------------------------------------------------------

    strong_database_signal = any(
        phrase in state_text
        for phrase in [
            "pool exhausted",
            "connection refused",
            "connection pool",
            "databaseconnection",
            "db pool",
        ]
    )

    if strong_database_signal:
        add_score(
            "inspect_database",
            8,
            "Strong database connection/pool evidence requires deeper investigation.",
        )

    # ---------------------------------------------------------
    # Evidence-driven stopping decision.
    # ---------------------------------------------------------

    sufficiency_decision = _assess_fallback_sufficiency(
            incident=incident,
            observations=observations,
            evidence=evidence,
            hypotheses=hypotheses,
            unused_tools=unused_tools,
            evidence_gaps=evidence_gaps,
            tools_used=tools_used,
        )

    if sufficiency_decision is not None:
        return sufficiency_decision



    # ---------------------------------------------------------
    # If no tool has meaningful evidence support, choose the
    # first unused tool only as a final deterministic fallback.
    # ---------------------------------------------------------

    if not tool_scores:
        # ---------------------------------------------------------
        # Explicit uncertainty must result in insufficient evidence.
        # Do not convert descriptive evidence into a root-cause
        # conclusion when the incident itself says the cause is unclear.
        # ---------------------------------------------------------
        incident_text = str(incident).lower()

        uncertainty_terms = [
            "unclear",
            "unknown",
            "not confirmed",
            "no confirmed",
            "underlying cause",
            "affected component",
            "cause is unclear",
        ]

        explicit_uncertainty = any(
            term in incident_text
            for term in uncertainty_terms
        )

        if explicit_uncertainty:
            return {
                "next_action": "insufficient_evidence",
                "reason": (
                    "Relevant investigation sources have been explored, "
                    "but the available evidence does not establish a "
                    "reliable root cause."
                ),
            }

        if _is_incident_evidence_aligned(
            incident=incident,
            evidence=evidence,
            hypotheses=hypotheses,
            observations=observations,
        ):
            return {
                "next_action": "finish",
                "reason": "Available evidence is sufficient to conclude the investigation.",
            }

        return {
            "next_action": "insufficient_evidence",
            "reason": "No relevant unused investigation tool remains.",
        }

    best_tool = max(
        tool_scores,
        key=tool_scores.get,
    )

    best_score = tool_scores[best_tool]

    # ---------------------------------------------------------
    # If there is no meaningful evidence signal, use the first
    # unused tool as a safe fallback.
    # ---------------------------------------------------------

    if best_score == 0:

        best_tool = unused_tools[0]

        return {
            "next_action": best_tool,
            "reason": (
                "Gemini was unavailable and the current evidence "
                "does not strongly prioritize one investigation source."
            ),
            "investigation_question": (
                "What additional evidence can this investigation source "
                "provide about the incident?"
            ),
            "confidence": "low",
        }

    reason_parts = tool_reasons.get(
        best_tool,
        [],
    )

    reason = (
        "Gemini was unavailable. The deterministic fallback selected "
        f"{best_tool} because the current investigation state indicates "
        "that this source can provide the most relevant unresolved evidence."
    )

    if reason_parts:
        reason += " " + " ".join(
            dict.fromkeys(reason_parts)
        )

    return {
        "next_action": best_tool,
        "reason": reason,
        "investigation_question": (
            f"What additional evidence from {best_tool} can confirm "
            "or weaken the strongest current hypotheses?"
        ),
        "confidence": "medium",
    }


def choose_next_tool(
    incident: str,
    observations: list,
    evidence: list,
    hypotheses: list,
    tools_used: list,
    evidence_gaps: list,
) -> dict:
    """
    Decide the next investigation action.

    The agent selects ONE action based on the evidence collected so far.
    """

    logger.info(
        "[InvestigationAgent] Deciding next investigation step..."
    )

    # ---------------------------------------------------------
    # Determine tools that have already been used
    # ---------------------------------------------------------

    used_tools = set(tools_used)

    unused_tools = [
        tool
        for tool in AVAILABLE_TOOLS
        if tool not in used_tools
    ]

    # ---------------------------------------------------------
    # Deterministic fast-path
    #
    # Avoid an expensive Gemini call when the current evidence
    # already gives the deterministic investigation logic a
    # sufficiently strong next action.
    # ---------------------------------------------------------

    fast_decision = _select_fallback_tool(
        incident=incident,
        observations=observations,
        evidence=evidence,
        hypotheses=hypotheses,
        unused_tools=unused_tools,
        evidence_gaps=evidence_gaps,
        tools_used=tools_used,
    )

    fast_action = fast_decision.get("next_action")

    if fast_action in {
        "finish",
        "insufficient_evidence",
    }:
        logger.info(
            "[InvestigationAgent] Deterministic fast-path selected: "
            f"{fast_action}"
        )
        return fast_decision

    # ---------------------------------------------------------
    # Build investigation context
    # ---------------------------------------------------------

    context = {
        "incident": incident,
        "tools_already_used": tools_used,
        "unused_tools": unused_tools,
        "observations": observations[-15:],
        "evidence": evidence[-20:],
        "hypotheses": hypotheses[-10:],
        "evidence_gaps": evidence_gaps[-15:],
    }

    # ---------------------------------------------------------
    # Gemini investigation decision prompt
    # ---------------------------------------------------------

    prompt = f"""
You are the Investigation Agent for IncidentIQ.

Your responsibility is to decide what investigation step
should happen NEXT.

You have access to these investigation tools:

- query_logs
- query_metrics
- get_deployments
- inspect_api
- inspect_database
- inspect_infrastructure
- inspect_security
- search_historical_incidents
- search_recent_commits

You may also decide:

- finish
- insufficient_evidence

INCIDENT:
{incident}

CURRENT INVESTIGATION STATE:
{json.dumps(context, indent=2, default=str)}

IMPORTANT DECISION RULES:

1. Choose ONLY ONE next action.

2. Use the current evidence, hypotheses, and evidence gaps
   to determine what information is most useful next.

3. Prefer an UNUSED investigation tool when it can provide
   new evidence relevant to an unresolved hypothesis.

4. DO NOT investigate every tool automatically.

5. DO NOT follow the tool list in a fixed order.

6. DO NOT repeatedly call a tool that has already been used
   if it would simply return the same type of evidence.

7. You may select an already-used tool ONLY when the existing
   evidence contains a specific unresolved question that
   genuinely requires another query.

8. If one hypothesis has substantially stronger evidence than
   the others, prioritize investigation that can confirm,
   weaken, or distinguish that hypothesis.

9. Evidence gaps should influence the next investigation step,
   but a gap alone is NOT sufficient reason to investigate.

10. Before selecting a tool, ask:
    "Can this tool provide evidence that would materially
    confirm, weaken, or distinguish the current leading hypothesis?"

11. Do NOT select a tool merely because that tool has a
    missing-data or telemetry gap.

12. If multiple independent evidence sources already support
    one hypothesis and no available unused tool is likely to
    distinguish that hypothesis from the alternatives, choose
    "finish".

13. If the current evidence is weak, mostly descriptive, or
    does not support a specific hypothesis, continue investigating
    using an unused tool that can provide relevant evidence.

14. Do NOT choose "finish" simply because one tool has already
    been investigated.

15. Choose "finish" only when the collected evidence supports
    a reasonable assessment, even if the confidence is medium
    rather than high.

16. Choose "insufficient_evidence" only when the available
    relevant investigation sources have been reasonably explored
    and the remaining evidence gaps cannot be resolved with
    the available tools.

17. If relevant unused tools remain and the current evidence
    does not support a specific root-cause hypothesis, prefer
    investigating those tools over prematurely choosing "finish".

18. Never claim that a hypothesis is proven simply because
    multiple signals are correlated.

19. Do not assume the incident description identifies the cause.
    Treat it as the investigation question, not as established fact.

20. Prefer efficient investigation over exhaustive investigation.

AVAILABLE UNUSED TOOLS:
{json.dumps(unused_tools)}

Return ONLY valid JSON:

{{
  "next_action": "query_logs|query_metrics|get_deployments|inspect_api|inspect_database|inspect_infrastructure|inspect_security|search_historical_incidents|finish|insufficient_evidence",
  "reason": "why this action is the best next step",
  "investigation_question": "specific question this action should answer",
  "confidence": "high|medium|low"
}}
"""

    # ---------------------------------------------------------
    # Call Gemini + evidence-driven fallback
    # ---------------------------------------------------------

    try:

        response = call_gemini(prompt)

        # -----------------------------------------------------
        # Parse Gemini response
        # -----------------------------------------------------

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

        decision = json.loads(
            text.strip()
        )

        if decision.get("next_action") == "finish":

            if not _finish_decision_is_supported(
                    incident=incident,
                    evidence=evidence,
                    hypotheses=hypotheses,
                    observations=observations,
                    unused_tools=unused_tools,
                    tools_used=tools_used,
                ):
                logger.warning(
                    "[InvestigationAgent] Gemini requested finish "
                    "without sufficient evidence. Applying fallback."
                )

                decision = _select_fallback_tool(
                    incident=incident,
                    observations=observations,
                    evidence=evidence,
                    hypotheses=hypotheses,
                    unused_tools=unused_tools,
                    tools_used=tools_used,
                    evidence_gaps=evidence_gaps,
                )

    except Exception as e:

        logger.warning(
            "[InvestigationAgent] Gemini unavailable or returned "
            f"invalid response: {e}"
        )

        decision = _select_fallback_tool(
            incident=incident,
            observations=observations,
            evidence=evidence,
            hypotheses=hypotheses,
            unused_tools=unused_tools,
            evidence_gaps=evidence_gaps,
            tools_used=tools_used,
        )
    # ---------------------------------------------------------
    # Safety validation
    # ---------------------------------------------------------

    valid_actions = set(AVAILABLE_TOOLS) | {
        "finish",
        "insufficient_evidence",
    }

    if decision.get("next_action") not in valid_actions:

        logger.warning(
            "[InvestigationAgent] Invalid action returned: "
            f"{decision.get('next_action')}"
        )

        decision = _select_fallback_tool(
            incident=incident,
            observations=observations,
            evidence=evidence,
            hypotheses=hypotheses,
            unused_tools=unused_tools,
            evidence_gaps=evidence_gaps,
            tools_used=tools_used,
        )

    # ---------------------------------------------------------
    # Prevent the agent from selecting an already-used tool
    # unless it explicitly has a reason to revisit it.
    # ---------------------------------------------------------

    selected_action = decision.get("next_action")

    if (
        selected_action in used_tools
        and selected_action not in {
            "finish",
            "insufficient_evidence",
        }
    ):

        logger.warning(
            "[InvestigationAgent] Selected tool was already used: "
            f"{selected_action}. Applying fallback."
        )

        decision = _select_fallback_tool(
            incident=incident,
            observations=observations,
            evidence=evidence,
            hypotheses=hypotheses,
            unused_tools=unused_tools,
            evidence_gaps=evidence_gaps,
            tools_used=tools_used,
        )
    logger.info(
        "[InvestigationAgent] Next action: "
        f"{decision.get('next_action')}"
    )

    return decision
