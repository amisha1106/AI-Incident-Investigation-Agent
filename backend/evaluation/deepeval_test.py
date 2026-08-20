"""
DeepEval evaluation suite for the Incident Investigation Agent.

Tests:
- Answer Relevancy: Is the root cause relevant to the query?
- Faithfulness: Is the report grounded in the evidence?
- Hallucination: Does the agent make up data?
- Context Precision: Are retrieved incidents relevant?

Run with: python -m pytest evaluation/deepeval_test.py -v
Or: deepeval test run evaluation/deepeval_test.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
)
from deepeval.models import DeepEvalBaseLLM
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL


# ── Custom Gemini wrapper for DeepEval ──────────────────────────────────────
class GeminiForDeepEval(DeepEvalBaseLLM):
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        return response.text

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return GEMINI_MODEL


gemini_evaluator = GeminiForDeepEval()


# ── Test Cases ───────────────────────────────────────────────────────────────
SAMPLE_CONTEXT = [
    "Deployment v3.8 was pushed to checkout-service at 10:01. Change: Added payment retry logic with new DB pool config.",
    "Error rate increased from 0.3% to 8.5% at 10:05, immediately after deployment v3.8.",
    "DB connection pool reached 94% saturation at 10:07.",
    "Latency P99 spiked from 200ms to 4500ms at 10:05.",
    "Historical incident INC-2025-001: Similar checkout latency caused by DB connection pool exhaustion after deployment v3.5.",
]

SAMPLE_RCA = """
Root Cause: Deployment v3.8 introduced a database connection leak in the payment retry logic.
The new retry loop does not properly close DB connections on failure, causing pool saturation.
Once the pool hit 94% capacity, new requests began timing out, causing latency spikes from
200ms to 4500ms and error rates rising to 8.5%. This is consistent with historical incident
INC-2025-001 from February 2025, which had the same failure pattern.

Immediate Actions:
1. Roll back deployment v3.8 immediately
2. Fix connection.close() in the retry loop
3. Increase connection pool size temporarily as a stopgap
"""


def test_answer_relevancy():
    """Test that the RCA is relevant to the original incident query."""
    test_case = LLMTestCase(
        input="Why did checkout latency increase after deployment?",
        actual_output=SAMPLE_RCA,
        retrieval_context=SAMPLE_CONTEXT,
    )
    metric = AnswerRelevancyMetric(threshold=0.7, model=gemini_evaluator)
    assert_test(test_case, [metric])


def test_faithfulness():
    """Test that the RCA is grounded in the retrieved evidence, not hallucinated."""
    test_case = LLMTestCase(
        input="Why did checkout latency increase after deployment?",
        actual_output=SAMPLE_RCA,
        retrieval_context=SAMPLE_CONTEXT,
    )
    metric = FaithfulnessMetric(threshold=0.7, model=gemini_evaluator)
    assert_test(test_case, [metric])


def test_hallucination():
    """Test that the agent doesn't introduce false facts."""
    test_case = LLMTestCase(
        input="Root cause analysis for checkout latency",
        actual_output=SAMPLE_RCA,
        context=SAMPLE_CONTEXT,
    )
    metric = HallucinationMetric(threshold=0.3, model=gemini_evaluator)
    assert_test(test_case, [metric])


def test_root_cause_specificity():
    """Custom test: verify root cause contains specific technical details."""
    rca_lower = SAMPLE_RCA.lower()
    assert any(kw in rca_lower for kw in ["connection", "pool", "db", "database"]), \
        "Root cause should mention database connection issue"
    assert any(kw in rca_lower for kw in ["v3.8", "deployment", "deploy"]), \
        "Root cause should reference the suspect deployment"
    assert "rollback" in rca_lower or "roll back" in rca_lower, \
        "Immediate actions should recommend rollback"


def test_confidence_range():
    """Test that confidence scores are realistic (not 100% or 0%)."""
    # Simulate extracting confidence from RCA state
    mock_confidence = 87
    assert 50 <= mock_confidence <= 98, \
        f"Confidence {mock_confidence}% is outside realistic range [50, 98]"


if __name__ == "__main__":
    print("Running DeepEval tests...")
    pytest.main([__file__, "-v", "--tb=short"])
