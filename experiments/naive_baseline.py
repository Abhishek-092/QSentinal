"""
Naive Multi-Detector Integration Baseline for QSENTINEL.

Implements a simple independent-threshold baseline: reject if ANY individual detector
exceeds its own threshold independently (Bonferroni-style composition).
This is the comparator that the joint calibration in Stage 2 is measured against.

Blueprint references: §12 (#5), §23 Phase 12.
"""
from __future__ import annotations

import numpy as np
from typing import Any

from qds.protocol import run_session
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1


def naive_threshold_decision(
    evidence,
    stage1_result,
    mismatch_threshold: float = 0.10,
    stage1_threshold: float = 3.841,
    investigate_fraction: float = 0.5,
) -> str:
    """
    Naive independent-threshold decision:
    - REJECT if mismatch_rate > threshold OR stage1 T > chi2_threshold
    - INVESTIGATE if either statistic exceeds half the threshold
    - ACCEPT otherwise

    This is the Bonferroni-style baseline that the joint calibration improves upon.
    """
    if stage1_result.statistic > stage1_threshold:
        return "FLAG_REJECT"
    if evidence.mismatch_rate > mismatch_threshold:
        return "FLAG_REJECT"
    if stage1_result.statistic > stage1_threshold * investigate_fraction:
        return "FLAG_INVESTIGATE"
    if evidence.mismatch_rate > mismatch_threshold * investigate_fraction:
        return "FLAG_INVESTIGATE"
    return "ACCEPT"


def run_naive_baseline(
    n_trials: int = 1000,
    n_qubits: int = 200,
    noise_p: float = 0.02,
    conditions: tuple[str, ...] = ("honest", "channel_manipulation", "low_and_slow_drift"),
) -> dict[str, dict[str, Any]]:
    """
    Run naive baseline across conditions and report detection rates.

    Returns per-condition dict with naive flag rate for comparison against
    the joint-calibrated Stage 2.
    """
    results = {}

    for condition in conditions:
        n_flagged = 0
        mismatch_rates = []
        stage1_Ts = []

        for t in range(n_trials):
            seed = t + 1000  # Fixed seed range for reproducibility
            attack = condition if condition != "honest" else None
            transcript = run_session(
                f"naive-{seed}", noise_p=noise_p, attack=attack,
                n_qubits=n_qubits, seed=seed,
            )

            evidence = extract_evidence(transcript)
            stage1_res = evaluate_stage1(evidence)
            verdict = naive_threshold_decision(evidence, stage1_res)

            if verdict != "ACCEPT":
                n_flagged += 1

            mismatch_rates.append(evidence.overall_mismatch_rate)
            stage1_Ts.append(stage1_res.statistic)

        mr = np.array(mismatch_rates)
        st = np.array(stage1_Ts)

        results[condition] = {
            "n_trials": n_trials,
            "naive_flag_rate": n_flagged / n_trials,
            "mean_mismatch_rate": float(np.mean(mr)),
            "mean_stage1_T": float(np.mean(st)),
        }

    return results
