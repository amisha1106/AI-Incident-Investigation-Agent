"""
Deployment Agent — correlates deployments with the incident timeline.
"""

import json
import re
from loguru import logger
from llm import call_gemini
from utils.parser import load_deployments, summarize_deployments


def run_deployment_agent(state: dict) -> dict:
    """
    LangGraph node: Deployment Analysis Agent.
    Finds deployments that correlate temporally with the incident.
    """
    plan = state.get("plan", {})
    metrics_findings = state.get("metrics_findings", {})
    logger.info("[DeploymentAgent] Analyzing deployment history...")

    deployments = load_deployments()
    if not deployments:
        return {
            **state,
            "deployment_findings": {"error": "No deployment data available."},
            "messages": state.get("messages", []) + [
                {"role": "deployment_agent", "content": "No deployment data found."}
            ],
        }

    summary = summarize_deployments(deployments)

    prompt = f"""
You are analyzing deployment history to find changes that may have caused a production incident.

Investigation context: {plan.get('incident_summary', 'Unknown incident')}
Metrics spike started at: {metrics_findings.get('raw_summary', {}).get('spike_start_time', 'unknown')}

Recent deployment history (most recent first):
{json.dumps(summary.get('recent_deployments', []), indent=2)}

Analyze these deployments:
1. Which deployment is most likely to have caused the incident?
2. What specific change in that deployment could cause the observed symptoms?
3. Is rollback available?
4. What is the time gap between the deployment and the incident spike?

Consider:
- Database config changes → connection pool issues
- Dependency upgrades → memory leaks, bugs
- Logic changes → increased query load
- Config changes → timeouts, circuit breakers

Return as JSON:
{{
  "suspect_deployment": {{
    "version": "v3.8",
    "service": "checkout-service",
    "timestamp": "...",
    "author": "...",
    "change_summary": "...",
    "rollback_available": true
  }},
  "risk_factor": "the specific change that is risky",
  "causal_mechanism": "how this change could cause the observed symptoms",
  "time_to_incident_minutes": 60,
  "confidence": "high|medium|low",
  "rollback_recommended": true,
  "other_deployments_at_risk": []
}}
"""

    response = call_gemini(prompt)

    try:
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```\s*$", "", text)
        findings = json.loads(text.strip())
    except Exception:
        findings = {"raw_analysis": response, "summary": summary}

    findings["raw_summary"] = summary

    suspect = findings.get("suspect_deployment", {})
    logger.info(f"[DeploymentAgent] Suspect deployment: {suspect.get('version')} - {suspect.get('service')}")

    return {
        **state,
        "deployment_findings": findings,
        "messages": state.get("messages", []) + [
            {"role": "deployment_agent", "content": f"Suspect deployment: {suspect.get('version')} ({suspect.get('change_summary', 'N/A')[:50]})"}
        ],
    }
