"""
IncidentIQ Investigation Tools.

These tools collect deterministic evidence from incident data sources.
They do not perform LLM reasoning.
"""

import pandas as pd

from loguru import logger

from utils.parser import (
    load_logs,
    summarize_logs,
    load_metrics,
    summarize_metrics,
    load_deployments,
    summarize_deployments,
)
from rag.vectorstore import retrieve_similar_incidents

def query_logs(incident: str) -> dict:
    """
    Query application logs and return structured evidence.

    Log facts are extracted deterministically from the available
    log data. No LLM call is made here.

    The Investigation Agent is responsible for reasoning over
    the evidence collected by this tool.
    """

    logger.info("[Tool:query_logs] Querying application logs...")

    logs = load_logs()

    if not logs:
        return {
            "tool": "query_logs",
            "status": "no_data",
            "evidence": [],
            "observations": [
                "No application log data is available."
            ],
            "hypotheses": [],
            "evidence_gaps": [
                "Application logs are unavailable."
            ],
            "error": "No log data available. Please seed data first.",
        }

    summary = summarize_logs(logs)

    evidence = []
    observations = []
    hypotheses = []
    evidence_gaps = []

    # ---------------------------------------------------------
    # Log counts
    # ---------------------------------------------------------

    total_logs = len(logs)

    error_logs = [
        log
        for log in logs
        if str(log.get("level", "")).upper() == "ERROR"
    ]

    warning_logs = [
        log
        for log in logs
        if str(log.get("level", "")).upper() in {
            "WARN",
            "WARNING",
        }
    ]

    observations.append(
        f"Total log entries analyzed: {total_logs}."
    )

    observations.append(
        f"ERROR entries: {len(error_logs)}."
    )

    observations.append(
        f"WARN entries: {len(warning_logs)}."
    )

    # ---------------------------------------------------------
    # Error patterns
    # ---------------------------------------------------------

    error_messages = []

    for log in error_logs:
        message = (
            log.get("message")
            or log.get("msg")
            or log.get("error")
        )

        if message:
            error_messages.append(
                str(message)
            )

    if error_messages:

        # Count repeated error messages
        error_counts = {}

        for message in error_messages:
            error_counts[message] = (
                error_counts.get(message, 0) + 1
            )

        sorted_errors = sorted(
            error_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        for message, count in sorted_errors[:5]:

            evidence.append(
                f"Error pattern: '{message}' occurred "
                f"{count} time(s)."
            )

    else:

        evidence_gaps.append(
            "No structured error messages were available "
            "for pattern analysis."
        )

    # ---------------------------------------------------------
    # Recent significant errors
    # ---------------------------------------------------------

    recent_errors = error_logs[-10:]

    for log in recent_errors:

        timestamp = (
            log.get("timestamp")
            or log.get("time")
            or log.get("datetime")
            or "unknown time"
        )

        message = (
            log.get("message")
            or log.get("msg")
            or log.get("error")
            or "unknown error"
        )

        evidence.append(
            f"ERROR at {timestamp}: {message}"
        )

    # ---------------------------------------------------------
    # Warning patterns
    # ---------------------------------------------------------

    if warning_logs:

        recent_warnings = warning_logs[-5:]

        for log in recent_warnings:

            timestamp = (
                log.get("timestamp")
                or log.get("time")
                or log.get("datetime")
                or "unknown time"
            )

            message = (
                log.get("message")
                or log.get("msg")
                or log.get("warning")
                or "unknown warning"
            )

            evidence.append(
                f"WARN at {timestamp}: {message}"
            )

    # ---------------------------------------------------------
    # Log timeline
    # ---------------------------------------------------------

    timestamps = []

    for log in logs:

        timestamp = (
            log.get("timestamp")
            or log.get("time")
            or log.get("datetime")
        )

        if timestamp:
            timestamps.append(
                str(timestamp)
            )

    if timestamps:

        observations.append(
            f"Log timeline spans from "
            f"{timestamps[0]} to {timestamps[-1]}."
        )

    else:

        evidence_gaps.append(
            "Log timestamps are unavailable, so a precise "
            "incident timeline cannot be established."
        )

    # ---------------------------------------------------------
    # Basic interpretation from deterministic facts
    # ---------------------------------------------------------

    if len(error_logs) > 0:

        hypotheses.append(
            "Application errors may be contributing to "
            "the reported incident."
        )

    if len(error_logs) == 0:

        observations.append(
            "No ERROR-level log entries were detected."
        )

    # ---------------------------------------------------------
    # Evidence gaps
    # ---------------------------------------------------------

    evidence_gaps.extend(
        [
            "Logs alone cannot establish the root cause.",
            "Distributed tracing information is unavailable.",
            "The relationship between individual errors "
            "and downstream dependencies is not established.",
        ]
    )

    # ---------------------------------------------------------
    # Return structured evidence
    # ---------------------------------------------------------

    return {
        "tool": "query_logs",
        "status": "success",
        "summary": summary,
        "analysis": {
            "incident": incident,
            "error_count": len(error_logs),
            "warning_count": len(warning_logs),
            "observations": observations,
            "evidence": evidence,
        },
        "evidence": evidence,
        "observations": observations,
        "hypotheses": hypotheses,
        "evidence_gaps": evidence_gaps,
    }

def query_metrics(incident: str) -> dict:
    """
    Query service metrics and return structured evidence.

    Metric facts are calculated deterministically from the data.
    No LLM call is made here.

    The Investigation Agent is responsible for reasoning over
    the evidence collected by this tool.
    """

    logger.info("[Tool:query_metrics] Querying service metrics...")

    metrics = load_metrics()

    if not metrics:
        return {
            "tool": "query_metrics",
            "status": "no_data",
            "evidence": [],
            "observations": [
                "No metrics data is available."
            ],
            "hypotheses": [],
            "evidence_gaps": [
                "Service metrics are unavailable."
            ],
            "error": "No metrics data available. Please seed data first.",
        }

    summary = summarize_metrics(metrics)

    evidence = []
    observations = []
    evidence_gaps = []

    # ---------------------------------------------------------
    # Latency
    # ---------------------------------------------------------

    latency_avg = summary.get("latency_p99_avg_ms")
    latency_max = summary.get("latency_p99_max_ms")

    if latency_avg is not None:
        observations.append(
            f"P99 latency average is {latency_avg} ms."
        )

    if latency_max is not None:
        evidence.append(
            f"P99 latency reached a maximum of {latency_max} ms."
        )

    if summary.get("latency_spike_detected"):
        observations.append(
            "A latency spike was detected."
        )

    # ---------------------------------------------------------
    # Error rate
    # ---------------------------------------------------------

    error_avg = summary.get("error_rate_avg_pct")
    error_max = summary.get("error_rate_max_pct")

    if error_avg is not None:
        observations.append(
            f"Average error rate is {error_avg}%."
        )

    if error_max is not None:
        evidence.append(
            f"Error rate reached a maximum of {error_max}%."
        )

    if summary.get("error_spike_detected"):
        observations.append(
            "An error-rate spike was detected."
        )

    # ---------------------------------------------------------
    # Database connection pool
    # ---------------------------------------------------------

    db_pool_max = summary.get(
        "db_connection_pool_max_pct"
    )

    if db_pool_max is not None:

        evidence.append(
            f"Database connection pool utilization "
            f"reached {db_pool_max}%."
        )

        if db_pool_max >= 90:
            observations.append(
                "Database connection pool utilization "
                "reached a critical level."
            )

            hypotheses.append(
                "Database connection pool saturation "
                "may be contributing to the incident."
            ) if False else None

    if summary.get("db_saturation_detected"):
        observations.append(
            "Database connection saturation was detected."
        )

    # ---------------------------------------------------------
    # Spike timing
    # ---------------------------------------------------------

    spike_start = summary.get(
        "spike_start_time"
    )

    if spike_start:
        evidence.append(
            f"Metric degradation was first detected around "
            f"{spike_start}."
        )

    # ---------------------------------------------------------
    # Detected anomalies
    # ---------------------------------------------------------

    anomalies = summary.get(
        "anomalies",
        []
    )

    if anomalies:

        evidence.extend(
            [
                f"Detected metric anomaly: {anomaly}"
                for anomaly in anomalies
            ]
        )

    # ---------------------------------------------------------
    # Evidence gaps
    # ---------------------------------------------------------

    evidence_gaps.extend(
        [
            "Metrics alone cannot establish the root cause.",
            "Application traces are unavailable.",
            "Individual database query execution times are unavailable.",
        ]
    )

    # ---------------------------------------------------------
    # Return structured evidence
    # ---------------------------------------------------------

    return {
        "tool": "query_metrics",
        "status": "success",
        "summary": summary,
        "analysis": {
            "incident": incident,
            "observations": observations,
            "evidence": evidence,
            "anomalies": anomalies,
        },
        "evidence": evidence,
        "observations": observations,
        "hypotheses": [],
        "evidence_gaps": evidence_gaps,
    }

def get_deployments(
    incident: str,
    investigation_context: str = ""
) -> dict:
    """
    Query deployment history and return structured evidence.

    Deployment facts are extracted deterministically from the
    available deployment data. No LLM call is made here.

    The Investigation Agent is responsible for reasoning over
    the evidence collected by this tool.
    """

    logger.info(
        "[Tool:get_deployments] Querying deployment history..."
    )

    deployments = load_deployments()

    if not deployments:
        return {
            "tool": "get_deployments",
            "status": "no_data",
            "evidence": [],
            "observations": [
                "No deployment data is available."
            ],
            "hypotheses": [],
            "evidence_gaps": [
                "Deployment history is unavailable."
            ],
            "error": "No deployment data available.",
        }

    summary = summarize_deployments(deployments)

    evidence = []
    observations = []
    hypotheses = []
    evidence_gaps = []

    # ---------------------------------------------------------
    # Recent deployments
    # ---------------------------------------------------------

    recent_deployments = summary.get(
        "recent_deployments",
        []
    )

    if not recent_deployments:
        evidence_gaps.append(
            "No recent deployment records are available."
        )

    for deployment in recent_deployments:

        version = (
            deployment.get("version")
            or deployment.get("deployment_version")
            or "unknown version"
        )

        service = (
            deployment.get("service")
            or deployment.get("service_name")
            or "unknown service"
        )

        timestamp = (
            deployment.get("timestamp")
            or deployment.get("time")
            or deployment.get("deployed_at")
            or "unknown time"
        )

        change = (
            deployment.get("change_summary")
            or deployment.get("changes")
            or deployment.get("description")
            or "change details unavailable"
        )

        rollback = deployment.get(
            "rollback_available"
        )

        evidence.append(
            f"Deployment {version} for {service} "
            f"occurred at {timestamp}."
        )

        evidence.append(
            f"Deployment {version} change: {change}."
        )

        if rollback is not None:

            observations.append(
                f"Deployment {version} rollback available: "
                f"{rollback}."
            )

    # ---------------------------------------------------------
    # Most recent deployment
    # ---------------------------------------------------------

    if recent_deployments:

        latest = recent_deployments[0]

        latest_version = (
            latest.get("version")
            or latest.get("deployment_version")
            or "unknown version"
        )

        latest_service = (
            latest.get("service")
            or latest.get("service_name")
            or "unknown service"
        )

        latest_timestamp = (
            latest.get("timestamp")
            or latest.get("time")
            or latest.get("deployed_at")
            or "unknown time"
        )

        observations.append(
            f"Latest available deployment is "
            f"{latest_version} for {latest_service} "
            f"at {latest_timestamp}."
        )

        hypotheses.append(
            "A recent deployment may be related to the "
            "incident if its timing and changes align with "
            "the observed degradation."
        )

    # ---------------------------------------------------------
    # Deployment count
    # ---------------------------------------------------------

    observations.append(
        f"{len(recent_deployments)} recent deployment record(s) "
        "were analyzed."
    )

    # ---------------------------------------------------------
    # Important limitation
    # ---------------------------------------------------------

    evidence_gaps.extend(
        [
            "Deployment history alone cannot establish causality.",
            "Exact deployment-to-incident timing may be unavailable.",
            "The actual code changes introduced by a deployment "
            "are not directly inspected.",
        ]
    )

    # ---------------------------------------------------------
    # Return structured evidence
    # ---------------------------------------------------------

    return {
        "tool": "get_deployments",
        "status": "success",
        "summary": summary,
        "analysis": {
            "incident": incident,
            "investigation_context": investigation_context,
            "recent_deployments": recent_deployments,
            "observations": observations,
            "evidence": evidence,
        },
        "evidence": evidence,
        "observations": observations,
        "hypotheses": hypotheses,
        "evidence_gaps": evidence_gaps,
    }

def inspect_api(incident: str) -> dict:
    """
    Inspect API behaviour and return structured evidence.

    This tool derives API-level evidence deterministically from the
    service metrics currently available to IncidentIQ.

    No LLM reasoning is performed here.

    The Investigation Agent is responsible for correlating this
    evidence with logs, deployments, database signals, and other
    investigation sources.
    """

    logger.info("[Tool:inspect_api] Inspecting API behaviour...")

    metrics = load_metrics()

    if not metrics:
        return {
            "tool": "inspect_api",
            "status": "no_data",
            "summary": {},
            "analysis": {
                "incident": incident,
            },
            "evidence": [],
            "observations": [
                "No API-related service metrics are available."
            ],
            "hypotheses": [],
            "evidence_gaps": [
                "API request telemetry is unavailable."
            ],
            "error": "No metrics data available. Please seed data first.",
        }

    summary = summarize_metrics(metrics)

    evidence = []
    observations = []
    hypotheses = []
    evidence_gaps = []

    # ---------------------------------------------------------
    # Request latency
    # ---------------------------------------------------------

    latency_avg = summary.get("latency_p99_avg_ms")
    latency_max = summary.get("latency_p99_max_ms")

    if latency_avg is not None:
        observations.append(
            f"API P99 latency averaged {latency_avg} ms."
        )

    if latency_max is not None:
        evidence.append(
            f"API P99 latency reached {latency_max} ms."
        )

    if summary.get("latency_spike_detected"):
        observations.append(
            "API latency degradation was detected."
        )

        hypotheses.append(
            "Elevated request latency may be contributing "
            "to the reported service degradation."
        )

    # ---------------------------------------------------------
    # Error behaviour
    # ---------------------------------------------------------

    error_avg = summary.get("error_rate_avg_pct")
    error_max = summary.get("error_rate_max_pct")

    if error_avg is not None:
        observations.append(
            f"Average API error rate was {error_avg}%."
        )

    if error_max is not None:
        evidence.append(
            f"API error rate reached {error_max}%."
        )

    if summary.get("error_spike_detected"):
        observations.append(
            "An API error-rate spike was detected."
        )

        hypotheses.append(
            "Increased API failures may be contributing "
            "to the incident."
        )

    # ---------------------------------------------------------
    # Degradation timing
    # ---------------------------------------------------------

    spike_start = summary.get("spike_start_time")

    if spike_start:
        evidence.append(
            f"API/service degradation was first detected around "
            f"{spike_start}."
        )

    # ---------------------------------------------------------
    # Request volume / throughput
    # ---------------------------------------------------------

    request_values = []

    request_fields = (
        "request_count",
        "requests",
        "request_rate",
        "requests_per_second",
        "rps",
        "throughput",
    )

    for metric in metrics:
        for field in request_fields:
            value = metric.get(field)

            if isinstance(value, (int, float)):
                request_values.append(float(value))
                break

    if request_values:
        avg_requests = sum(request_values) / len(request_values)
        max_requests = max(request_values)

        observations.append(
            f"Average recorded API request volume was "
            f"{avg_requests:.2f}."
        )

        evidence.append(
            f"Maximum recorded API request volume was "
            f"{max_requests:.2f}."
        )

        if avg_requests > 0 and max_requests >= avg_requests * 2:
            hypotheses.append(
                "A request-volume spike may have contributed "
                "to API degradation."
            )

    else:
        evidence_gaps.append(
            "Request volume or throughput metrics are unavailable."
        )

    # ---------------------------------------------------------
    # HTTP status information
    # ---------------------------------------------------------

    status_fields = (
        "status_code",
        "http_status",
        "response_status",
    )

    status_counts = {}

    for metric in metrics:
        status_code = None

        for field in status_fields:
            value = metric.get(field)

            if value is not None:
                status_code = str(value)
                break

        if status_code:
            status_counts[status_code] = (
                status_counts.get(status_code, 0) + 1
            )

    if status_counts:
        for status_code, count in sorted(
            status_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]:
            evidence.append(
                f"HTTP status {status_code} appeared "
                f"{count} time(s) in API telemetry."
            )

        server_errors = sum(
            count
            for code, count in status_counts.items()
            if code.startswith("5")
        )

        client_errors = sum(
            count
            for code, count in status_counts.items()
            if code.startswith("4")
        )

        if server_errors:
            observations.append(
                f"{server_errors} server-side HTTP 5xx "
                "response(s) were observed."
            )

            hypotheses.append(
                "Server-side API failures may be contributing "
                "to the incident."
            )

        if client_errors:
            observations.append(
                f"{client_errors} HTTP 4xx response(s) "
                "were observed."
            )

    else:
        evidence_gaps.append(
            "Per-request HTTP status-code telemetry is unavailable."
        )

    # ---------------------------------------------------------
    # Timeout signals
    # ---------------------------------------------------------

    timeout_fields = (
        "timeout_count",
        "timeouts",
        "request_timeouts",
    )

    timeout_values = []

    for metric in metrics:
        for field in timeout_fields:
            value = metric.get(field)

            if isinstance(value, (int, float)):
                timeout_values.append(float(value))
                break

    if timeout_values:
        total_timeouts = sum(timeout_values)

        evidence.append(
            f"Recorded API timeout count across the available "
            f"telemetry was {total_timeouts:.0f}."
        )

        if total_timeouts > 0:
            observations.append(
                "API request timeouts were detected."
            )

            hypotheses.append(
                "Request timeouts may be contributing "
                "to the service degradation."
            )

    else:
        evidence_gaps.append(
            "Explicit API timeout metrics are unavailable."
        )

    # ---------------------------------------------------------
    # Rate-limit signals
    # ---------------------------------------------------------

    rate_limit_fields = (
        "rate_limit_count",
        "rate_limited_requests",
        "http_429_count",
    )

    rate_limit_values = []

    for metric in metrics:
        for field in rate_limit_fields:
            value = metric.get(field)

            if isinstance(value, (int, float)):
                rate_limit_values.append(float(value))
                break

    if rate_limit_values:
        total_rate_limited = sum(rate_limit_values)

        evidence.append(
            f"Recorded rate-limited request count was "
            f"{total_rate_limited:.0f}."
        )

        if total_rate_limited > 0:
            observations.append(
                "API rate limiting was observed."
            )

            hypotheses.append(
                "Rate limiting may be affecting request success "
                "or latency."
            )

    else:
        evidence_gaps.append(
            "Rate-limit telemetry is unavailable."
        )

    # ---------------------------------------------------------
    # Endpoint-level telemetry
    # ---------------------------------------------------------

    endpoint_fields = (
        "endpoint",
        "route",
        "path",
        "api_endpoint",
    )

    endpoints = {}

    for metric in metrics:
        endpoint = None

        for field in endpoint_fields:
            value = metric.get(field)

            if value:
                endpoint = str(value)
                break

        if endpoint:
            endpoints[endpoint] = endpoints.get(endpoint, 0) + 1

    if endpoints:
        top_endpoints = sorted(
            endpoints.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]

        for endpoint, count in top_endpoints:
            evidence.append(
                f"API endpoint '{endpoint}' appeared in "
                f"{count} telemetry record(s)."
            )

    else:
        evidence_gaps.append(
            "Endpoint-level API telemetry is unavailable."
        )

    # ---------------------------------------------------------
    # Cross-signal interpretation
    # ---------------------------------------------------------

    if (
        summary.get("latency_spike_detected")
        and summary.get("error_spike_detected")
    ):
        hypotheses.append(
            "The simultaneous increase in API latency and error rate "
            "suggests a service or downstream dependency degradation."
        )

    # ---------------------------------------------------------
    # Important limitations
    # ---------------------------------------------------------

    evidence_gaps.extend(
        [
            "Distributed request traces are unavailable.",
            "Upstream and downstream API dependency timing is unavailable.",
            "API gateway access logs are not currently connected.",
        ]
    )

    # Remove duplicates while preserving order.
    evidence = list(dict.fromkeys(evidence))
    observations = list(dict.fromkeys(observations))
    hypotheses = list(dict.fromkeys(hypotheses))
    evidence_gaps = list(dict.fromkeys(evidence_gaps))

    # ---------------------------------------------------------
    # Structured result
    # ---------------------------------------------------------

    return {
        "tool": "inspect_api",
        "status": "success",
        "summary": {
            "latency_p99_avg_ms": latency_avg,
            "latency_p99_max_ms": latency_max,
            "error_rate_avg_pct": error_avg,
            "error_rate_max_pct": error_max,
            "latency_spike_detected": bool(
                summary.get("latency_spike_detected")
            ),
            "error_spike_detected": bool(
                summary.get("error_spike_detected")
            ),
            "spike_start_time": spike_start,
            "http_status_counts": status_counts,
            "request_telemetry_available": bool(request_values),
            "endpoint_telemetry_available": bool(endpoints),
        },
        "analysis": {
            "incident": incident,
            "observations": observations,
            "evidence": evidence,
            "hypotheses": hypotheses,
            "evidence_gaps": evidence_gaps,
        },
        "evidence": evidence,
        "observations": observations,
        "hypotheses": hypotheses,
        "evidence_gaps": evidence_gaps,
    }

def inspect_database(incident: str) -> dict:
    """
    Investigate database behaviour relevant to an incident.

    Uses deterministic analysis of available metrics and application logs.
    This tool does not perform LLM reasoning.
    """

    logger.info("[Tool:inspect_database] Inspecting database behaviour...")

    evidence = []
    observations = []
    hypotheses = []
    evidence_gaps = []

    # ---------------------------------------------------------
    # Load available data
    # ---------------------------------------------------------

    metrics_df = load_metrics()
    logs_df = load_logs()

    if metrics_df is None and logs_df is None:
        return {
            "tool": "inspect_database",
            "status": "no_data",
            "summary": "No database-related metrics or logs are available.",
            "analysis": {},
            "evidence": [],
            "observations": [
                "Database investigation could not be performed because no source data is available."
            ],
            "hypotheses": [],
            "evidence_gaps": [
                "Database metrics are unavailable.",
                "Application logs are unavailable.",
                "Database connection telemetry is unavailable.",
            ],
        }

    # ---------------------------------------------------------
    # Metrics analysis
    # ---------------------------------------------------------

    if metrics_df is not None:

        metrics_summary = summarize_metrics(metrics_df)

        # Database connection pool
        pool_avg = metrics_summary.get("db_pool_utilization_avg")
        pool_max = metrics_summary.get("db_pool_utilization_max")

        if pool_avg is not None:
            evidence.append(
                f"Average database connection pool utilization was "
                f"{pool_avg}%."
            )

        if pool_max is not None:
            evidence.append(
                f"Database connection pool utilization reached "
                f"{pool_max}%."
            )

            observations.append(
                f"Database connection pool utilization reached "
                f"{pool_max}%."
            )

            if pool_max >= 90:
                hypotheses.append(
                    "Database connection pool saturation may be contributing "
                    "to the incident."
                )

        # Database query latency
        db_query_avg = metrics_summary.get("db_query_latency_avg_ms")
        db_query_max = metrics_summary.get("db_query_latency_max_ms")

        if db_query_avg is not None:
            evidence.append(
                f"Average database query latency was "
                f"{db_query_avg} ms."
            )

        if db_query_max is not None:
            evidence.append(
                f"Maximum database query latency reached "
                f"{db_query_max} ms."
            )

            if db_query_max > 1000:
                hypotheses.append(
                    "Elevated database query latency may be contributing "
                    "to service degradation."
                )

        # Database-related anomalies
        anomalies = metrics_summary.get("anomalies", [])

        for anomaly in anomalies:

            anomaly_text = str(anomaly).lower()

            if any(
                keyword in anomaly_text
                for keyword in [
                    "db",
                    "database",
                    "connection",
                    "pool",
                    "query",
                ]
            ):
                evidence.append(
                    f"Detected database-related metric anomaly: {anomaly}"
                )

    else:
        evidence_gaps.append(
            "Database metrics are unavailable."
        )

    # ---------------------------------------------------------
    # Application log analysis
    # ---------------------------------------------------------

    if logs_df is not None:

        logs_summary = summarize_logs(logs_df)

        top_errors = logs_summary.get("top_errors", [])

        database_errors_found = False

        for error in top_errors:

            message = str(error.get("message", ""))
            count = error.get("count", 0)

            message_lower = message.lower()

            if any(
                keyword in message_lower
                for keyword in [
                    "database",
                    "db",
                    "connection",
                    "pool",
                    "query",
                    "jdbc",
                    "sql",
                ]
            ):

                database_errors_found = True

                evidence.append(
                    f"Database error pattern: '{message}' "
                    f"occurred {count} time(s)."
                )

        if database_errors_found:

            observations.append(
                "Application logs contain repeated database-related errors."
            )

            hypotheses.append(
                "Database connectivity or connection-management issues "
                "may be contributing to the incident."
            )

    else:
        evidence_gaps.append(
            "Application logs are unavailable for database error analysis."
        )

    # ---------------------------------------------------------
    # Cross-signal interpretation
    # ---------------------------------------------------------

    has_pool_evidence = any(
        "pool" in str(item).lower()
        for item in evidence
    )

    has_connection_errors = any(
        any(
            keyword in str(item).lower()
            for keyword in [
                "connection",
                "database error pattern",
                "connection refused",
                "pool exhausted",
                "timeout",
                "retry",
            ]
        )
        for item in evidence
    )

    if has_pool_evidence and has_connection_errors:

        observations.append(
            "Database connection-pool pressure and repeated "
            "database-related errors are present together."
        )

        hypotheses.append(
            "Connection-pool pressure combined with repeated connection "
            "errors may be contributing to API latency and failures."
        )

    # ---------------------------------------------------------
    # Explicit limitations
    # ---------------------------------------------------------

    evidence_gaps.extend(
        [
            "Direct database connection inspection is unavailable.",
            "Individual database query execution plans are unavailable.",
            "Database lock/wait information is unavailable.",
            "Database CPU and memory telemetry are unavailable.",
        ]
    )

    # ---------------------------------------------------------
    # No evidence case
    # ---------------------------------------------------------

    if not evidence:

        evidence_gaps.extend(
            [
                "No database-specific evidence was found in the available telemetry.",
                "Database connection state could not be directly inspected.",
                "Database-level query execution details are unavailable.",
            ]
        )

    # ---------------------------------------------------------
    # Deduplicate
    # ---------------------------------------------------------

    evidence = list(dict.fromkeys(evidence))
    observations = list(dict.fromkeys(observations))
    hypotheses = list(dict.fromkeys(hypotheses))
    evidence_gaps = list(dict.fromkeys(evidence_gaps))

    # ---------------------------------------------------------
    # Return structured investigation result
    # ---------------------------------------------------------

    return {
        "tool": "inspect_database",
        "status": "success",
        "summary": (
            "Database investigation completed using available "
            "metrics and application logs."
        ),
        "analysis": {
            "incident": incident,
            "database_evidence_found": bool(evidence),
        },
        "evidence": evidence,
        "observations": observations,
        "hypotheses": hypotheses,
        "evidence_gaps": evidence_gaps,
    }

def inspect_infrastructure(incident: str) -> dict:
    """
    Investigate infrastructure-level signals relevant to an incident.

    The current dataset does not contain direct infrastructure telemetry
    such as CPU, memory, disk, host, node, or container metrics.

    This tool therefore reports infrastructure evidence availability
    and explicit evidence gaps rather than inferring infrastructure
    health from unrelated service metrics.
    """

    logger.info(
        "[Tool:inspect_infrastructure] Inspecting infrastructure behaviour..."
    )

    evidence = []
    observations = []
    hypotheses = []
    evidence_gaps = []

    metrics_df = load_metrics()

    if metrics_df is None:
        return {
            "tool": "inspect_infrastructure",
            "status": "no_data",
            "summary": (
                "Infrastructure investigation could not be performed "
                "because metrics are unavailable."
            ),
            "analysis": {
                "incident": incident,
                "infrastructure_telemetry_available": False,
            },
            "evidence": [],
            "observations": [],
            "hypotheses": [],
            "evidence_gaps": [
                "Infrastructure metrics are unavailable.",
                "CPU utilization telemetry is unavailable.",
                "Memory utilization telemetry is unavailable.",
                "Disk utilization telemetry is unavailable.",
                "Host and node health telemetry is unavailable.",
            ],
        }

    metrics_summary = summarize_metrics(metrics_df)

    # ---------------------------------------------------------
    # Check which infrastructure signals are actually available
    # ---------------------------------------------------------

    infrastructure_fields = {
        "cpu_utilization": [
            "cpu_utilization_avg",
            "cpu_utilization_max",
        ],
        "memory_utilization": [
            "memory_utilization_avg",
            "memory_utilization_max",
        ],
        "disk_utilization": [
            "disk_utilization_avg",
            "disk_utilization_max",
        ],
        "host_health": [
            "host_health",
            "node_health",
        ],
    }

    available_signals = []

    for signal_name, fields in infrastructure_fields.items():

        if any(
            metrics_summary.get(field) is not None
            for field in fields
        ):
            available_signals.append(signal_name)

    # ---------------------------------------------------------
    # Current dataset: no direct infrastructure telemetry
    # ---------------------------------------------------------

    if not available_signals:

        observations.append(
            "No direct infrastructure-level telemetry is available "
            "in the current metrics dataset."
        )

        evidence_gaps.extend(
            [
                "CPU utilization telemetry is unavailable.",
                "Memory utilization telemetry is unavailable.",
                "Disk utilization telemetry is unavailable.",
                "Host-level health telemetry is unavailable.",
                "Node-level health telemetry is unavailable.",
                "Container resource telemetry is unavailable.",
                "Container restart history is unavailable.",
                "Infrastructure event history is unavailable.",
            ]
        )

    else:

        evidence.append(
            "Infrastructure telemetry is available for: "
            + ", ".join(available_signals)
            + "."
        )

        observations.append(
            "Direct infrastructure telemetry is available "
            "for further investigation."
        )

    # ---------------------------------------------------------
    # Avoid duplicating database/API evidence
    # ---------------------------------------------------------

    evidence_gaps.extend(
        [
            "Infrastructure-level CPU, memory, and disk behaviour "
            "cannot currently be evaluated.",
            "Host/node resource saturation cannot currently be confirmed "
            "or ruled out.",
        ]
    )

    # ---------------------------------------------------------
    # Deduplicate
    # ---------------------------------------------------------

    evidence = list(dict.fromkeys(evidence))
    observations = list(dict.fromkeys(observations))
    hypotheses = list(dict.fromkeys(hypotheses))
    evidence_gaps = list(dict.fromkeys(evidence_gaps))

    return {
        "tool": "inspect_infrastructure",
        "status": "success",
        "summary": (
            "Infrastructure investigation completed based on the "
            "currently available telemetry."
        ),
        "analysis": {
            "incident": incident,
            "infrastructure_telemetry_available": bool(
                available_signals
            ),
            "available_signals": available_signals,
        },
        "evidence": evidence,
        "observations": observations,
        "hypotheses": hypotheses,
        "evidence_gaps": evidence_gaps,
    }

def inspect_security(
    incident: str | None = None,
    investigation_context: dict | None = None,
) -> dict:
    """
    Inspect available security-related signals.

    The tool only reports security evidence that is actually
    available in the current incident data. It does not infer
    security incidents from unrelated application metrics.
    """

    logger.info("[Tool:inspect_security] Inspecting security signals...")

    context = investigation_context or {}

    logs = context.get("logs", [])

    evidence = []
    observations = []
    hypotheses = []
    evidence_gaps = []

    security_keywords = [
        "authentication",
        "authorization",
        "unauthorized",
        "forbidden",
        "access denied",
        "login failed",
        "invalid token",
        "token expired",
        "permission denied",
        "credential",
        "security",
        "rate limit",
        "blocked",
        "suspicious",
        "attack",
    ]

    security_events = []

    for log in logs:
        message = str(
            log.get("message", log.get("error", log))
        )

        message_lower = message.lower()

        if any(
            keyword in message_lower
            for keyword in security_keywords
        ):
            security_events.append(message)

    if security_events:

        for event in security_events[:20]:
            evidence.append(
                f"Security-related log signal: {event}"
            )

        observations.append(
            "Security-related signals are present in the available logs."
        )

        hypotheses.append(
            "Authentication, authorization, or other security-related "
            "issues may be contributing to the incident."
        )

    else:

        observations.append(
            "No direct security-related signals were found in the "
            "available incident logs."
        )

        evidence_gaps.extend([
            "Dedicated authentication telemetry is unavailable.",
            "Authorization and permission telemetry is unavailable.",
            "Security event or audit logs are unavailable.",
            "Threat-detection telemetry is unavailable.",
        ])

    return {
        "tool": "inspect_security",
        "status": "success",
        "summary": (
            "Security investigation completed using the "
            "available incident telemetry."
        ),
        "analysis": {
            "security_telemetry_available": bool(security_events),
            "security_signal_count": len(security_events),
        },
        "evidence": evidence,
        "observations": observations,
        "hypotheses": hypotheses,
        "evidence_gaps": evidence_gaps,
    }

def search_historical_incidents(
    incident: str | None = None,
    investigation_context: dict | None = None,
) -> dict:
    """
    Search historical incidents for semantically similar cases.

    This tool retrieves historical incidents only.
    It does not perform root-cause reasoning.
    """

    logger.info(
        "[Tool:search_historical_incidents] "
        "Searching historical incidents..."
    )

    query = incident or ""

    if not query.strip():
        return {
            "tool": "search_historical_incidents",
            "status": "success",
            "summary": "No incident query was provided for historical search.",
            "analysis": {
                "historical_search_available": False,
                "result_count": 0,
            },
            "evidence": [],
            "observations": [],
            "hypotheses": [],
            "evidence_gaps": [
                "No incident description was available for historical search."
            ],
        }

    try:
        # Lazy import:
        # ChromaDB is loaded only when this tool is actually used.
        from rag.vectorstore import retrieve_similar_incidents

        results = retrieve_similar_incidents(query)

        evidence = []
        observations = []

        for result in results:
            metadata = result.get("metadata", {})
            similarity = result.get("similarity_score")

            evidence.append(
                {
                    "incident_id": metadata.get("incident_id", "unknown"),
                    "title": metadata.get("title"),
                    "service": metadata.get("service"),
                    "date": metadata.get("date"),
                    "similarity_score": similarity,
                    "document": result.get("document"),
                }
            )

            observations.append(
                (
                    f"Historical incident '{metadata.get('title', 'unknown')}' "
                    f"has similarity score {similarity}."
                )
            )

        return {
            "tool": "search_historical_incidents",
            "status": "success",
            "summary": (
                f"Historical incident search returned "
                f"{len(results)} similar incident(s)."
            ),
            "analysis": {
                "historical_search_available": True,
                "result_count": len(results),
            },
            "evidence": evidence,
            "observations": observations,
            "hypotheses": [],
            "evidence_gaps": [],
        }

    except Exception as exc:
        logger.exception(
            "Historical incident retrieval failed."
        )

        return {
            "tool": "search_historical_incidents",
            "status": "unavailable",
            "summary": (
                "Historical incident search is currently unavailable."
            ),
            "analysis": {
                "historical_search_available": False,
                "result_count": 0,
            },
            "evidence": [],
            "observations": [
                "Historical incident retrieval could not be completed."
            ],
            "hypotheses": [],
            "evidence_gaps": [
                (
                    "Historical incident search is currently unavailable "
                    "because the local retrieval environment failed to "
                    "initialize."
                ),
                (
                    "No historical incidents were used in this investigation."
                ),
            ],
        }