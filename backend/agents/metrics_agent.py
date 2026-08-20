"""
Metrics Analysis Agent — analyzes time-series metrics for anomalies.
"""

import json
import re
from loguru import logger
from llm import call_gemini
from utils.parser import load_metrics, summarize_metrics


def run_metrics_agent(state: dict) -> dict:
    """
    LangGraph node: Metrics Analysis Agent.
    Analyzes latency, error rate, CPU, memory, and DB metrics.
    """
    plan = state.get("plan", {})
    logger.info("[MetricsAgent] Analyzing service metrics...")

    metrics = load_metrics()
    if not metrics:
        return {
            **state,
            "metrics_findings": {"error": "No metrics data available."},
            "messages": state.get("messages", []) + [
                {"role": "metrics_agent", "content": "No metrics data found."}
            ],
        }

    summary = summarize_metrics(metrics)

    prompt = f"""
You are analyzing production service metrics to investigate an incident.

Investigation context: {plan.get('incident_summary', 'Unknown incident')}
Symptoms reported: {plan.get('symptoms', [])}

Metrics Summary:
- Latency P99 average: {summary.get('latency_p99_avg_ms')}ms
- Latency P99 max: {summary.get('latency_p99_max_ms')}ms
- Latency spike detected: {summary.get('latency_spike_detected')}
- Error rate average: {summary.get('error_rate_avg_pct')}%
- Error rate max: {summary.get('error_rate_max_pct')}%
- Error spike detected: {summary.get('error_spike_detected')}
- DB connection pool max: {summary.get('db_connection_pool_max_pct')}%
- DB saturation detected: {summary.get('db_saturation_detected')}
- Spike started at: {summary.get('spike_start_time')}

Detected anomalies:
{json.dumps(summary.get('anomalies', []), indent=2)}

Analyze these metrics and provide:
1. What metrics show clear anomalies?
2. What is the sequence of metric degradation (which broke first)?
3. Is CPU/memory involved (resource exhaustion) or is it application-level?
4. What does the DB connection pool saturation suggest?
5. How does the spike timing correlate with known deployments?

Return as JSON:
{{
  "primary_anomaly": "the most significant metric anomaly",
  "anomaly_sequence": "order in which metrics degraded",
  "resource_exhaustion": true or false,
  "bottleneck": "db|cpu|memory|network|application",
  "spike_timing": "when the spike started relative to deployments",
  "root_cause_hypothesis": "what metrics suggest is wrong",
  "confidence": "high|medium|low",
  "key_metrics": ["metric1: value", "metric2: value"]
}}
"""

    response = call_gemini(prompt)

    try:
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```\s*$", "", text)
        findings = json.loads(text.strip())
    except Exception:
        findings = {"raw_analysis": response}

    findings["raw_summary"] = summary

    logger.info(f"[MetricsAgent] Bottleneck identified: {findings.get('bottleneck', 'unknown')}")

    return {
        **state,
        "metrics_findings": findings,
        "messages": state.get("messages", []) + [
            {"role": "metrics_agent", "content": f"Metrics analysis: bottleneck={findings.get('bottleneck')}, confidence={findings.get('confidence')}"}
        ],
    }
