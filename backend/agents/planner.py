"""
Planner Agent — entry point of the LangGraph workflow.
Analyzes the user query and creates a structured investigation plan.
"""

import json
import re
from pathlib import Path
from loguru import logger
from llm import call_gemini
from config import PROMPTS_DIR


def parse_json_from_llm(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    # Remove markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Fallback: extract first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def run_planner(state: dict) -> dict:
    """
    LangGraph node: Planner Agent.
    Input state keys: query
    Output state keys: plan, messages
    """
    query = state.get("query", "")
    logger.info(f"[Planner] Analyzing query: '{query[:80]}...'")

    system_prompt = (PROMPTS_DIR / "planner.txt").read_text()

    prompt = f"""
User incident query: {query}

Analyze this query and return a structured investigation plan as JSON.
"""

    response = call_gemini(prompt, system_prompt)

    try:
        plan = parse_json_from_llm(response)
    except Exception as e:
        logger.warning(f"[Planner] Failed to parse JSON, using fallback: {e}")
        plan = {
            "incident_summary": query[:100],
            "symptoms": ["latency increase", "error rate increase"],
            "affected_service": "checkout-service",
            "time_window": "unknown",
            "investigation_steps": [
                "Check logs for errors",
                "Analyze latency metrics",
                "Review recent deployments",
            ],
            "rag_query": query,
            "priority": "high",
        }

    logger.info(f"[Planner] Plan created: {plan.get('incident_summary', '')}")

    return {
        **state,
        "plan": plan,
        "messages": state.get("messages", []) + [
            {"role": "planner", "content": f"Investigation plan created: {plan.get('incident_summary')}"}
        ],
    }
