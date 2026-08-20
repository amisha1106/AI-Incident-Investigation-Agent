"""
Synthetic data generator for demo purposes.
Generates realistic logs, metrics, deployments, and historical incidents.
No external dependencies needed — pure Python.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger


SERVICES = ["checkout-service", "payment-gateway", "user-auth", "inventory-api", "notification-service"]
ERROR_TYPES = [
    "ConnectionTimeoutException",
    "DatabaseConnectionLeakError",
    "NullPointerException",
    "OutOfMemoryError",
    "CircuitBreakerOpenException",
    "SlowQueryException",
]
DEPLOYMENTS = [
    {"version": "v3.8", "service": "checkout-service", "author": "priya.sharma", "change": "Added payment retry logic with new DB pool config"},
    {"version": "v2.1", "service": "payment-gateway", "author": "rahul.dev", "change": "Upgraded JDBC driver to 8.0.33"},
    {"version": "v4.2", "service": "user-auth", "author": "ananya.k", "change": "JWT expiry reduced to 15 min for security"},
    {"version": "v1.9", "service": "inventory-api", "author": "vikas.r", "change": "Bulk insert optimization using batch transactions"},
    {"version": "v5.0", "service": "notification-service", "author": "deepa.m", "change": "Switched from SQS to Kafka for event streaming"},
]

HISTORICAL_INCIDENTS = [
    {
        "id": "INC-2025-001",
        "date": "2025-02-14",
        "title": "Checkout latency spike after v3.5 deployment",
        "service": "checkout-service",
        "root_cause": "Database connection pool exhaustion due to missing connection.close() in retry loop. "
                      "Connections accumulated until pool was saturated, causing 30s timeouts.",
        "resolution": "Rolled back v3.5, fixed connection leak, redeployed as v3.5.1. "
                      "Added connection pool monitoring alert.",
        "duration_minutes": 45,
        "impact": "High — 8000 users affected, $12k revenue loss",
        "signals": ["error_rate > 5%", "latency_p99 > 5000ms", "db_connections > 90%"],
        "tags": ["db-connection-leak", "checkout", "latency"],
    },
    {
        "id": "INC-2025-002",
        "date": "2025-03-22",
        "title": "Payment gateway OOM crash",
        "service": "payment-gateway",
        "root_cause": "JDBC driver upgrade introduced a result-set caching bug that cached large LOB objects in heap. "
                      "Memory grew unbounded until JVM OOM kill.",
        "resolution": "Downgraded JDBC driver to 8.0.28. Added -Xmx heap limit and OOM alerting.",
        "duration_minutes": 20,
        "impact": "Critical — all payments failed for 20 minutes",
        "signals": ["jvm_heap > 95%", "gc_pause > 2000ms", "error_rate > 80%"],
        "tags": ["oom", "jdbc", "payment"],
    },
    {
        "id": "INC-2025-003",
        "date": "2025-04-10",
        "title": "Auth service latency increase",
        "service": "user-auth",
        "root_cause": "JWT expiry reduction to 15 min caused 4x increase in token refresh calls, "
                      "overloading Redis cache and causing cache stampede.",
        "resolution": "Reverted JWT expiry to 1 hour. Implemented staggered token refresh with jitter.",
        "duration_minutes": 30,
        "impact": "Medium — 2000 users required re-login",
        "signals": ["redis_hit_rate < 40%", "auth_latency_p95 > 800ms"],
        "tags": ["jwt", "cache-stampede", "auth"],
    },
    {
        "id": "INC-2025-004",
        "date": "2025-05-05",
        "title": "Inventory API slow queries after batch migration",
        "service": "inventory-api",
        "root_cause": "Bulk insert optimization removed explicit transaction commits, causing table-level locks "
                      "to persist for entire batch duration (up to 5 min), blocking read queries.",
        "resolution": "Added explicit commit every 1000 rows. Added read replica for inventory reads.",
        "duration_minutes": 60,
        "impact": "Medium — inventory reads degraded, no data loss",
        "signals": ["db_lock_wait > 30s", "query_latency_p95 > 8000ms"],
        "tags": ["slow-query", "db-lock", "inventory"],
    },
    {
        "id": "INC-2025-005",
        "date": "2025-06-18",
        "title": "Notification service message loss after Kafka migration",
        "service": "notification-service",
        "root_cause": "Kafka consumer group was misconfigured with auto-commit enabled and processing time "
                      "exceeding session.timeout.ms, causing rebalances and message loss.",
        "resolution": "Disabled auto-commit, implemented manual offset commit after processing. "
                      "Increased session.timeout.ms to 60s.",
        "duration_minutes": 90,
        "impact": "High — ~15000 notifications dropped",
        "signals": ["kafka_consumer_lag > 10000", "notification_delivery_rate < 50%"],
        "tags": ["kafka", "message-loss", "notification"],
    },
]


def generate_logs(incident_service: str, incident_time: datetime, error_type: str, count: int = 50) -> list[dict]:
    """Generate realistic log entries around an incident."""
    logs = []
    for i in range(count):
        offset_minutes = random.randint(-30, 60)
        ts = incident_time + timedelta(minutes=offset_minutes)
        is_error = offset_minutes > 0 and random.random() < 0.4

        if is_error:
            logs.append({
                "timestamp": ts.isoformat(),
                "level": "ERROR",
                "service": incident_service,
                "message": f"{error_type}: {random.choice(['Connection refused', 'Timeout after 30s', 'Pool exhausted (max=20)', 'Retry limit exceeded'])}",
                "thread": f"worker-{random.randint(1, 16)}",
                "trace_id": f"tr-{random.randint(100000, 999999)}",
            })
        else:
            logs.append({
                "timestamp": ts.isoformat(),
                "level": random.choice(["INFO", "INFO", "INFO", "WARN"]),
                "service": incident_service,
                "message": random.choice([
                    "Request processed successfully",
                    f"DB query took {random.randint(5, 200)}ms",
                    "Health check OK",
                    "Cache hit ratio: 87%",
                    "Batch job started",
                ]),
                "thread": f"worker-{random.randint(1, 16)}",
                "trace_id": f"tr-{random.randint(100000, 999999)}",
            })

    return sorted(logs, key=lambda x: x["timestamp"])


def generate_metrics(incident_time: datetime, spike_metric: str = "latency") -> list[dict]:
    """Generate time-series metrics with a realistic spike pattern."""
    metrics = []
    for minutes_offset in range(-60, 120, 5):
        ts = incident_time + timedelta(minutes=minutes_offset)
        is_incident = minutes_offset > 0

        if spike_metric == "latency":
            latency_p50 = random.randint(80, 120) if not is_incident else random.randint(400, 3000)
            latency_p99 = random.randint(200, 400) if not is_incident else random.randint(2000, 8000)
            error_rate = round(random.uniform(0.1, 0.5), 2) if not is_incident else round(random.uniform(3.5, 12.0), 2)
            db_connections = random.randint(10, 30) if not is_incident else random.randint(75, 100)
        else:
            latency_p50 = random.randint(80, 150)
            latency_p99 = random.randint(200, 500)
            error_rate = round(random.uniform(0.1, 0.5), 2)
            db_connections = random.randint(10, 30)

        metrics.append({
            "timestamp": ts.isoformat(),
            "latency_p50_ms": latency_p50,
            "latency_p99_ms": latency_p99,
            "error_rate_pct": error_rate,
            "requests_per_second": random.randint(200, 800),
            "cpu_pct": random.randint(15, 45),
            "memory_pct": random.randint(40, 65),
            "db_connection_pool_pct": db_connections,
            "cache_hit_rate_pct": random.randint(75, 95) if not is_incident else random.randint(30, 60),
        })

    return metrics


def generate_deployment_history(incident_time: datetime, service: str, version: str) -> list[dict]:
    """Generate deployment history with the incident-causing deployment included."""
    deployments = []
    # Add some older deployments
    for i in range(3, 0, -1):
        old_deploy = random.choice(DEPLOYMENTS)
        deployments.append({
            "timestamp": (incident_time - timedelta(days=i * 7)).isoformat(),
            "service": service,
            "version": f"v{random.randint(1, 3)}.{random.randint(0, 7)}",
            "author": old_deploy["author"],
            "status": "success",
            "change_summary": old_deploy["change"],
            "rollback_available": True,
        })

    # The incident-causing deployment — 1 hour before incident
    match = next((d for d in DEPLOYMENTS if d["service"] == service), DEPLOYMENTS[0])
    deployments.append({
        "timestamp": (incident_time - timedelta(hours=1)).isoformat(),
        "service": service,
        "version": version,
        "author": match["author"],
        "status": "success",
        "change_summary": match["change"],
        "rollback_available": True,
    })

    return sorted(deployments, key=lambda x: x["timestamp"])


def seed_data(data_dir: Path, incident_time: datetime = None) -> dict:
    """
    Seed all data directories with synthetic incident data.
    Returns a summary of what was generated.
    """
    if incident_time is None:
        incident_time = datetime.now() - timedelta(hours=3)

    service = "checkout-service"
    version = "v3.8"
    error_type = "DatabaseConnectionLeakError"

    # Write logs
    logs = generate_logs(service, incident_time, error_type)
    log_file = data_dir / "logs" / "app_logs.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(json.dumps(logs, indent=2))

    # Write metrics
    metrics = generate_metrics(incident_time, spike_metric="latency")
    metrics_file = data_dir / "metrics" / "service_metrics.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    metrics_file.write_text(json.dumps(metrics, indent=2))

    # Write deployments
    deployments = generate_deployment_history(incident_time, service, version)
    deploy_file = data_dir / "deployments" / "deploy_history.json"
    deploy_file.parent.mkdir(parents=True, exist_ok=True)
    deploy_file.write_text(json.dumps(deployments, indent=2))

    # Write historical incidents (for RAG)
    incidents_file = data_dir / "incidents" / "historical_incidents.json"
    incidents_file.parent.mkdir(parents=True, exist_ok=True)
    incidents_file.write_text(json.dumps(HISTORICAL_INCIDENTS, indent=2))

    logger.info(f"Seeded data: {len(logs)} logs, {len(metrics)} metric points, {len(deployments)} deployments, {len(HISTORICAL_INCIDENTS)} historical incidents")

    return {
        "logs": len(logs),
        "metrics": len(metrics),
        "deployments": len(deployments),
        "historical_incidents": len(HISTORICAL_INCIDENTS),
        "incident_time": incident_time.isoformat(),
        "service": service,
        "version": version,
    }


if __name__ == "__main__":
    from pathlib import Path
    result = seed_data(Path(__file__).parent.parent / "data")
    print(json.dumps(result, indent=2))
