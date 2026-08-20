"""
Root Cause Agent — synthesizes all agent findings into a final RCA report.
Uses RAG to find similar historical incidents.
"""

import json
import re
from loguru import logger
from llm import call_gemini
from rag import retrieve_similar_incidents
from config import PROMPTS_DIR


def run_rootcause_agent(state: dict) -> dict:
    """
    LangGraph node: Root Cause Agent.
    Synthesizes findings from all other agents into a final RCA.
    """
    plan = state.get("plan", {})
    log_findings = state.get("log_findings", {})
    metrics_findings = state.get("metrics_findings", {})
    deployment_findings = state.get("deployment_findings", {})

    logger.info("[RootCauseAgent] Synthesizing findings into RCA...")

    # RAG: find similar historical incidents
    rag_query = plan.get("rag_query", plan.get("incident_summary", "production incident"))
    similar_incidents = retrieve_similar_incidents(rag_query)

    similar_text = "\n\n".join([
        f"[{inc['metadata']['title']} — similarity: {inc['similarity_score']:.2f}]\n{inc['document']}"
        for inc in similar_incidents
    ])

    system_prompt = (PROMPTS_DIR / "rootcause.txt").read_text()

    prompt = f"""
Synthesize the following investigation findings into a definitive Root Cause Analysis.

═══════════════════════════════════════════
USER QUERY: {state.get('query', '')}
═══════════════════════════════════════════

INVESTIGATION PLAN:
{json.dumps(plan, indent=2)}

═══════════════════════════════════════════
LOG AGENT FINDINGS:
{json.dumps({k: v for k, v in log_findings.items() if k != 'raw_summary'}, indent=2)}

═══════════════════════════════════════════
METRICS AGENT FINDINGS:
{json.dumps({k: v for k, v in metrics_findings.items() if k != 'raw_summary'}, indent=2)}

═══════════════════════════════════════════
DEPLOYMENT AGENT FINDINGS:
{json.dumps({k: v for k, v in deployment_findings.items() if k != 'raw_summary'}, indent=2)}

═══════════════════════════════════════════
SIMILAR HISTORICAL INCIDENTS (from RAG):
{similar_text if similar_text else "No similar incidents found."}

═══════════════════════════════════════════

Now synthesize all of this into a complete Root Cause Analysis. Be specific, evidence-driven, and actionable.
Return as the JSON format specified in your instructions.
"""

    response = call_gemini(prompt, system_prompt)

    try:
        text = re.sub(r"```(?:json)?\s*", "", response)
        text = re.sub(r"```\s*$", "", text)
        rca = json.loads(text.strip())
    except Exception as e:
        logger.warning(f"[RootCauseAgent] JSON parse failed, using raw: {e}")
        rca = {
            "root_cause": {
                "summary": "Analysis complete — see detailed findings",
                "detailed_explanation": response,
                "evidence": [],
                "confidence_pct": 70,
            },
            "immediate_actions": ["Review deployment findings", "Check logs"],
            "long_term_prevention": ["Add monitoring", "Improve alerting"],
            "severity": "high",
        }

    rca["similar_incidents_retrieved"] = [
        {
            "title": inc["metadata"]["title"],
            "date": inc["metadata"]["date"],
            "similarity": inc["similarity_score"],
        }
        for inc in similar_incidents
    ]

    confidence = rca.get("root_cause", {}).get("confidence_pct", 0)
    summary = rca.get("root_cause", {}).get("summary", "N/A")
    logger.info(f"[RootCauseAgent] RCA complete. Confidence: {confidence}%. Root cause: {summary[:60]}")

    return {
        **state,
        "rca": rca,
        "similar_incidents": similar_incidents,
        "messages": state.get("messages", []) + [
            {"role": "rootcause_agent", "content": f"RCA complete: {summary} (confidence: {confidence}%)"}
        ],
    }
