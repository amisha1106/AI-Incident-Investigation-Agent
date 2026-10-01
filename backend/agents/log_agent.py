"""
Investigation tools used by the IncidentIQ Investigation Agent.

These functions collect evidence from different production sources.
They do not decide the root cause.
"""

import json
import re

from loguru import logger

from llm import call_gemini
from utils.parser import load_logs, summarize_logs


def query_logs(incident: str) -> dict:
    """
    Query application logs and return structured evidence.

    The tool:
    1. Loads available logs
    2. Summarizes them programmatically
    3. Sends a limited sample to Gemini for interpretation
    4. Returns evidence for the Investigation Agent

    It does NOT make the final RCA decision.
    """

    logger.info("[Tool:query_logs] Querying application logs...")

    logs = load_logs()

    if not logs:
        return {
            "tool": "query_logs",
            "status": "no_data",
            "evidence": [],
            "observations": [
                "No log data is available."
            ],
            "error": "No log data available. Please seed data first.",
        }

    summary = summarize_logs(logs)

    # Keep the LLM input bounded.
    error_logs = [
        log for log in logs
        if log.get("level") == "ERROR"
    ][-20:]

    warn_logs = [
        log for log in logs
        if log.get("level") == "WARN"
    ][-10:]

    prompt = f"""
You are a production incident investigation tool analyzing application logs.

Incident:
{incident}

Log Summary:
- Total entries: {summary['total_log_entries']}
- Error count: {summary['error_count']} ({summary['error_rate_pct']}%)
- Warning count: {summary['warning_count']}
- Services affected: {summary['services_affected']}
- Top errors: {json.dumps(summary['top_errors'], indent=2)}
- Time range: {summary['time_range']}

Recent ERROR entries:
{json.dumps(error_logs[:10], indent=2)}

Recent WARN entries:
{json.dumps(warn_logs[:5], indent=2)}

Analyze only what the logs support.

Identify:
1. Significant error patterns
2. Important observations
3. Possible hypotheses suggested by the logs
4. Supporting evidence
5. Timeline information
6. Remaining evidence gaps

Do not claim that a hypothesis is proven.

Return JSON:
{{
  "error_pattern": "description",
  "observations": ["observation1", "observation2"],
  "hypotheses": ["possible explanation 1", "possible explanation 2"],
  "evidence": ["supporting evidence 1", "supporting evidence 2"],
  "timeline": "when the important pattern appears",
  "confidence": "high|medium|low",
  "evidence_gaps": ["what cannot be determined from logs"]
}}
"""

    response = call_gemini(prompt)

    try:
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```\s*$", "", text)

        analysis = json.loads(text.strip())

    except Exception:
        logger.warning(
            "[Tool:query_logs] Gemini returned non-JSON response."
        )

        analysis = {
            "raw_analysis": response
        }

    logger.info("[Tool:query_logs] Log evidence collected.")

    return {
        "tool": "query_logs",
        "status": "success",
        "summary": summary,
        "analysis": analysis,
        "evidence": analysis.get("evidence", []),
        "observations": analysis.get("observations", []),
        "hypotheses": analysis.get("hypotheses", []),
        "evidence_gaps": analysis.get("evidence_gaps", []),
    }