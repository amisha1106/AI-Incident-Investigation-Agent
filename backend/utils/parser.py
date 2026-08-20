"""
Utility functions for parsing logs, metrics and deployment data.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any
from loguru import logger
from config import LOGS_DIR, METRICS_DIR, DEPLOYMENTS_DIR


def load_json(path: Path) -> Any:
    """Safe JSON loader with error handling."""
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return []


def load_logs() -> list[dict]:
    log_file = LOGS_DIR / "app_logs.json"
    if not log_file.exists():
        return []
    return load_json(log_file)


def load_metrics() -> list[dict]:
    metrics_file = METRICS_DIR / "service_metrics.json"
    if not metrics_file.exists():
        return []
    return load_json(metrics_file)


def load_deployments() -> list[dict]:
    deploy_file = DEPLOYMENTS_DIR / "deploy_history.json"
    if not deploy_file.exists():
        return []
    return load_json(deploy_file)


def summarize_logs(logs: list[dict]) -> dict:
    """Extract key statistics from raw log entries."""
    total = len(logs)
    errors = [l for l in logs if l.get("level") == "ERROR"]
    warnings = [l for l in logs if l.get("level") == "WARN"]

    error_messages = {}
    for e in errors:
        msg = e.get("message", "")[:60]
        error_messages[msg] = error_messages.get(msg, 0) + 1

    top_errors = sorted(error_messages.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_log_entries": total,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "error_rate_pct": round(len(errors) / total * 100, 2) if total else 0,
        "top_errors": [{"message": m, "count": c} for m, c in top_errors],
        "services_affected": list({l.get("service", "unknown") for l in logs}),
        "time_range": {
            "start": logs[0]["timestamp"] if logs else None,
            "end": logs[-1]["timestamp"] if logs else None,
        },
    }


def summarize_metrics(metrics: list[dict]) -> dict:
    """Detect anomalies in metric time series."""
    if not metrics:
        return {}

    latencies = [m["latency_p99_ms"] for m in metrics]
    errors = [m["error_rate_pct"] for m in metrics]
    db_conns = [m["db_connection_pool_pct"] for m in metrics]

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    avg_error = sum(errors) / len(errors)
    max_error = max(errors)
    max_db = max(db_conns)

    # Find the spike start time
    spike_threshold = avg_latency * 2
    spike_entries = [m for m in metrics if m["latency_p99_ms"] > spike_threshold]

    return {
        "latency_p99_avg_ms": round(avg_latency, 1),
        "latency_p99_max_ms": max_latency,
        "latency_spike_detected": max_latency > spike_threshold,
        "error_rate_avg_pct": round(avg_error, 2),
        "error_rate_max_pct": max_error,
        "error_spike_detected": max_error > 2.0,
        "db_connection_pool_max_pct": max_db,
        "db_saturation_detected": max_db > 80,
        "spike_start_time": spike_entries[0]["timestamp"] if spike_entries else None,
        "anomalies": _detect_anomalies(metrics),
    }


def _detect_anomalies(metrics: list[dict]) -> list[str]:
    anomalies = []
    for m in metrics:
        if m["latency_p99_ms"] > 2000:
            anomalies.append(f"Latency spike: {m['latency_p99_ms']}ms at {m['timestamp'][:16]}")
        if m["error_rate_pct"] > 3.0:
            anomalies.append(f"Error spike: {m['error_rate_pct']}% at {m['timestamp'][:16]}")
        if m["db_connection_pool_pct"] > 80:
            anomalies.append(f"DB pool near saturation: {m['db_connection_pool_pct']}% at {m['timestamp'][:16]}")
    return anomalies[:8]  # top 8


def summarize_deployments(deployments: list[dict]) -> dict:
    """Find recent deployments that may correlate with incidents."""
    if not deployments:
        return {}

    recent = sorted(deployments, key=lambda x: x["timestamp"], reverse=True)[:5]
    return {
        "total_deployments": len(deployments),
        "recent_deployments": recent,
        "most_recent": recent[0] if recent else None,
        "services_deployed": list({d["service"] for d in deployments}),
    }
