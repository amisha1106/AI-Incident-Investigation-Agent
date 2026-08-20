"""
RAGAS evaluation for the RAG pipeline (historical incident retrieval).

Metrics:
- Context Precision: Retrieved incidents are relevant
- Context Recall: All relevant incidents are retrieved
- Answer Relevancy: Final answer matches the query
- Faithfulness: Answer is grounded in retrieved context

Usage: python evaluation/ragas_eval.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    answer_relevancy,
    faithfulness,
)
from loguru import logger


# ── Evaluation Dataset ───────────────────────────────────────────────────────
# Format: question, answer, contexts (retrieved), ground_truth
EVAL_DATASET = [
    {
        "question": "Why did checkout latency increase after a new deployment?",
        "answer": (
            "Deployment v3.8 introduced a database connection leak in the payment retry logic. "
            "The retry loop failed to close DB connections, causing pool saturation (94%). "
            "Once saturated, new requests timed out, causing latency to spike from 200ms to 4500ms "
            "and error rate to rise to 8.5%. This matches historical incident INC-2025-001 "
            "which had an identical failure pattern."
        ),
        "contexts": [
            "Incident INC-2025-001 Date: 2025-02-14 Title: Checkout latency spike after v3.5 deployment "
            "Root Cause: Database connection pool exhaustion due to missing connection.close() in retry loop.",
            "Deployment v3.8 was pushed to checkout-service. Change: Added payment retry logic with new DB pool config.",
            "DB connection pool reached 94% saturation. Latency P99 spiked to 4500ms.",
        ],
        "ground_truth": (
            "The root cause was a database connection leak introduced by deployment v3.8. "
            "Connections were not being closed in the retry loop, leading to connection pool exhaustion."
        ),
    },
    {
        "question": "What caused payment gateway to crash with out of memory error?",
        "answer": (
            "A JDBC driver upgrade to version 8.0.33 introduced a result-set caching bug that stored "
            "large LOB objects in heap memory. Memory grew unbounded until the JVM was killed by OOM. "
            "The resolution was to downgrade to JDBC 8.0.28 and add -Xmx heap limits."
        ),
        "contexts": [
            "Incident INC-2025-002 Date: 2025-03-22 Title: Payment gateway OOM crash "
            "Root Cause: JDBC driver upgrade introduced a result-set caching bug that cached large LOB objects in heap.",
            "Deployment v2.1 to payment-gateway. Change: Upgraded JDBC driver to 8.0.33.",
        ],
        "ground_truth": (
            "JDBC driver version 8.0.33 had a caching bug that caused unbounded heap growth, "
            "leading to JVM OOM. Downgrading the driver resolved the issue."
        ),
    },
    {
        "question": "Why did notification service lose messages after Kafka migration?",
        "answer": (
            "The Kafka consumer group was misconfigured with auto-commit enabled. "
            "When processing time exceeded session.timeout.ms, Kafka triggered rebalances "
            "and messages were lost. The fix was to disable auto-commit and implement "
            "manual offset commit after successful processing."
        ),
        "contexts": [
            "Incident INC-2025-005 Date: 2025-06-18 Title: Notification service message loss after Kafka migration "
            "Root Cause: Kafka consumer group was misconfigured with auto-commit enabled and processing time "
            "exceeding session.timeout.ms, causing rebalances and message loss.",
            "Deployment v5.0 to notification-service. Change: Switched from SQS to Kafka for event streaming.",
        ],
        "ground_truth": (
            "Kafka consumer auto-commit combined with slow processing caused rebalances and message loss. "
            "Manual offset commit after processing resolved it."
        ),
    },
]


def run_ragas_evaluation():
    """Run RAGAS evaluation on the RAG pipeline."""
    logger.info("Starting RAGAS evaluation...")

    dataset = Dataset.from_list(EVAL_DATASET)

    try:
        results = evaluate(
            dataset,
            metrics=[
                context_precision,
                context_recall,
                answer_relevancy,
                faithfulness,
            ],
        )

        print("\n" + "="*60)
        print("RAGAS EVALUATION RESULTS")
        print("="*60)
        print(f"Context Precision:  {results['context_precision']:.3f}")
        print(f"Context Recall:     {results['context_recall']:.3f}")
        print(f"Answer Relevancy:   {results['answer_relevancy']:.3f}")
        print(f"Faithfulness:       {results['faithfulness']:.3f}")

        avg = sum([
            results['context_precision'],
            results['context_recall'],
            results['answer_relevancy'],
            results['faithfulness'],
        ]) / 4
        print(f"\nOverall RAG Score:  {avg:.3f}")
        print("="*60)

        return results

    except Exception as e:
        logger.error(f"RAGAS evaluation failed: {e}")
        logger.info("Note: RAGAS requires an OpenAI API key by default. "
                    "To use Gemini with RAGAS, configure a custom LLM wrapper.")
        return None


if __name__ == "__main__":
    run_ragas_evaluation()
