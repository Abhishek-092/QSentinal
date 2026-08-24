"""
Verification Accuracy Evaluator for QSENTINEL.

Legitimate-session acceptance-rate sweep across a range of honest noise levels.
This is a distinct PS-141 deliverable (F10): "verification accuracy analysis"
reported separately from attack-condition false-positive results.

Blueprint references: §5 (#24), F10, §16, §23 Phase 12.
"""
from __future__ import annotations

import numpy as np
from typing import Any

from qds.protocol import run_session
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1
from qsentinel_monitor.orchestrator import analyze


def sweep_acceptance(
    p_values: tuple[float, ...] = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10),
    n_trials: int = 500,
    n_qubits: int = 200,
) -> dict[float, dict[str, Any]]:
    """
    For each honest noise level p, run n_trials sessions and report:
    - protocol acceptance rate (deterministic, from protocol itself)
    - monitor ACCEPT rate (advisory verdict)
    - mean mismatch rate
    - mean Stage 1 statistic T
    """
    results = {}

    for p in p_values:
        protocol_accepted = 0
        monitor_accepted = 0
        mismatch_rates = []
        stage1_Ts = []
        stage1_passed_count = 0

        for t in range(n_trials):
            seed = int(p * 100000 + t)
            transcript = run_session(
                f"verify-{seed}", noise_p=p, n_qubits=n_qubits, seed=seed
            )

            # Protocol-level decision
            if transcript.protocol_decision.accepted:
                protocol_accepted += 1

            # Monitor-level decision
            monitoring = analyze(transcript, transcript.protocol_decision)
            if monitoring.verdict == "ACCEPT":
                monitor_accepted += 1

            # Evidence metrics
            evidence = extract_evidence(transcript)
            stage1_res = evaluate_stage1(evidence)

            mismatch_rates.append(evidence.overall_mismatch_rate)
            stage1_Ts.append(stage1_res.statistic)
            if stage1_res.passed:
                stage1_passed_count += 1

        n = n_trials
        mr = np.array(mismatch_rates)
        st = np.array(stage1_Ts)

        results[p] = {
            "noise_p": p,
            "n_trials": n_trials,
            "protocol_acceptance_rate": protocol_accepted / n,
            "monitor_accept_rate": monitor_accepted / n,
            "stage1_pass_rate": stage1_passed_count / n,
            "mean_mismatch_rate": float(np.mean(mr)),
            "std_mismatch_rate": float(np.std(mr)),
            "mean_stage1_T": float(np.mean(st)),
            "max_stage1_T": float(np.max(st)),
        }

    return results


def format_verification_sweep(results: dict[float, dict[str, Any]]) -> str:
    """Format verification accuracy sweep as a readable table."""
    lines = []
    lines.append("Verification Accuracy Sweep — Legitimate Sessions Across Noise Levels")
    lines.append("=" * 95)
    lines.append(f"{'p':>6} {'Prot.Acc':>10} {'Mon.Accept':>11} {'S1.Pass':>9} {'Mean m':>10} {'Mean T':>10} {'Max T':>10}")
    lines.append("-" * 95)

    for p, r in sorted(results.items()):
        lines.append(
            f"{p:>6.3f} "
            f"{r['protocol_acceptance_rate']:>10.4f} "
            f"{r['monitor_accept_rate']:>11.4f} "
            f"{r['stage1_pass_rate']:>9.4f} "
            f"{r['mean_mismatch_rate']:>10.6f} "
            f"{r['mean_stage1_T']:>10.4f} "
            f"{r['max_stage1_T']:>10.4f}"
        )

    return "\n".join(lines)
