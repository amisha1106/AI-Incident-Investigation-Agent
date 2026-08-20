"""
Log Analysis Agent — examines application logs for error patterns.
"""

import json
from loguru import logger
from llm import call_gemini
from utils.parser import load_logs, summarize_logs


def run_log_agent(state: dict) -> dict:
    """
    LangGraph node: Log Analysis Agent.
    Loads logs, summarizes them, and uses Gemini to extract insights.
    """
    plan = state.get("plan", {})
    logger.info("[LogAgent] Analyzing application logs...")

    logs = load_logs()
    if not logs:
        return {
            **state,
            "log_findings": {"error": "No log data available. Please seed data first."},
            "messages": state.get("messages", []) + [
                {"role": "log_agent", "content": "No log data found."}
            ],
        }

    summary = summarize_logs(logs)

    # Take last 20 error logs for LLM analysis (avoid token overload)
    error_logs = [l for l in logs if l.get("level") == "ERROR"][-20:]
    warn_logs = [l for l in logs if l.get("level") == "WARN"][-10:]

    prompt = f"""
You are analyzing application logs for a production incident.

Investigation context: {plan.get('incident_summary', 'Unknown incident')}
Suspected symptoms: {plan.get('symptoms', [])}

Log Summary:
- Total entries: {summary['total_log_entries']}
- Error count: {summary['error_count']} ({summary['error_rate_pct']}%)
- Warning count: {summary['warning_count']}
- Services affected: {summary['services_affected']}
- Top errors: {json.dumps(summary['top_errors'], indent=2)}
- Time range: {summary['time_range']}

Recent ERROR log entries (sample):
{json.dumps(error_logs[:10], indent=2)}

Recent WARN log entries (sample):
{json.dumps(warn_logs[:5], indent=2)}

Based on these logs, provide your analysis:
1. What errors are most significant?
2. What is the error pattern (sudden spike? gradual increase? specific thread/service?)
3. What does the error message suggest as root cause?
4. How confident are you in these log-based findings?

Return as JSON:
{{
  "error_pattern": "description of the error pattern",
  "most_significant_errors": ["error1", "error2"],
  "root_cause_hypothesis": "what logs suggest is wrong",
  "confidence": "high|medium|low",
  "key_evidence": ["evidence1", "evidence2"],
  "log_based_timeline": "when errors started and pattern over time"
}}
"""

    response = call_gemini(prompt)

    try:
        import re
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```\s*$", "", text)
        findings = json.loads(text.strip())
    except Exception:
        findings = {"raw_analysis": response, "summary": summary}

    findings["raw_summary"] = summary

    logger.info(f"[LogAgent] Analysis complete. Hypothesis: {findings.get('root_cause_hypothesis', 'N/A')[:60]}")

    return {
        **state,
        "log_findings": findings,
        "messages": state.get("messages", []) + [
            {"role": "log_agent", "content": f"Log analysis complete: {findings.get('root_cause_hypothesis', 'See findings')}"}
        ],
    }
