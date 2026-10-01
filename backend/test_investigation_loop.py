from agents.orchestrator import run_investigation_loop


if __name__ == "__main__":

    incident = (
        "Checkout service latency has increased significantly "
        "after the latest deployment."
    )

    result = run_investigation_loop(incident)

    print("\n" + "=" * 70)
    print("INCIDENTIQ INVESTIGATION RESULT")
    print("=" * 70)

    print("\nTools Used:")
    for tool in result["tools_used"]:
        print(f"  → {tool}")

    print("\nObservations:")
    for observation in result["observations"]:
        print(f"  → {observation}")

    print("\nEvidence:")
    for item in result["evidence"]:
        print(f"  → {item}")

    print("\nHypotheses:")
    for hypothesis in result["hypotheses"]:
        print(f"  → {hypothesis}")

    print("\nEvidence Gaps:")
    for gap in result["evidence_gaps"]:
        print(f"  → {gap}")

    print(f"\nConfidence: {result['confidence']}")

    print("\n" + "=" * 70)