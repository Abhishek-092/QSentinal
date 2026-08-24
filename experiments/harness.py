"""
7-Condition Monte Carlo Harness for QSENTINEL evaluation.

Runs the standard 7 attack conditions at N trials each using multiprocessing with
the explicit 'spawn' context for cross-platform reproducibility (Blueprint §10).

Blueprint references: §5 (#22), §16, §23 Phase 9.
"""
from __future__ import annotations

import multiprocessing
import numpy as np
from typing import Any

from qds.protocol import run_session
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1
from experiments.seed_allocator import SeedAllocator
from experiments.config import AttackCondition, STANDARD_CONDITIONS


def _run_single_trial(args: tuple) -> dict[str, Any]:
    """Execute a single Monte Carlo trial. Designed for pool.map (must be top-level function)."""
    condition_name, strategy, seed, n_qubits, noise_p = args

    if strategy == "honest":
        transcript = run_session(
            f"trial-{seed}", noise_p=noise_p, n_qubits=n_qubits, seed=seed
        )
    else:
        transcript = run_session(
            f"trial-{seed}", noise_p=noise_p, attack=strategy,
            n_qubits=n_qubits, seed=seed,
        )

    evidence = extract_evidence(transcript)
    stage1_res = evaluate_stage1(evidence)

    return {
        "session_id": transcript.session_id,
        "protocol_accepted": transcript.protocol_decision.accepted,
        "mismatch_count": transcript.protocol_decision.mismatch_count,
        "sifted_length": transcript.protocol_decision.sifted_length,
        "mismatch_rate": evidence.overall_mismatch_rate,
        "stage1_passed": stage1_res.passed,
        "stage1_T": stage1_res.statistic,
        "stage1_p_hat": stage1_res.best_fit_p,
        "condition": condition_name,
    }


def run_all_conditions(
    n_trials: int = 1000,
    n_workers: int | None = None,
    n_qubits: int = 200,
    noise_p: float = 0.02,
    conditions: tuple[AttackCondition, ...] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Run all attack conditions at N trials each.

    Returns per-condition detection-rate table with:
    - protocol_acceptance_rate
    - stage1_rejection_rate
    - mean/std mismatch_rate
    - 95% confidence intervals on key metrics
    """
    if conditions is None:
        conditions = STANDARD_CONDITIONS

    if n_workers is None:
        n_workers = min(multiprocessing.cpu_count(), 8)

    # Build trial argument list with seed allocation
    trial_args = []
    for condition in conditions:
        for t in range(n_trials):
            seed = SeedAllocator.get_seed("EVALUATION", len(trial_args))
            trial_args.append((
                condition.name,
                condition.strategy,
                seed,
                n_qubits,
                noise_p,
            ))

    # Execute with spawn context for reproducibility
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=n_workers) as pool:
        results = pool.map(_run_single_trial, trial_args)

    # Aggregate per condition
    idx = 0
    tables = {}
    for condition in conditions:
        condition_results = results[idx:idx + n_trials]
        idx += n_trials

        n_protocol_accepted = sum(1 for r in condition_results if r["protocol_accepted"])
        n_stage1_passed = sum(1 for r in condition_results if r["stage1_passed"])
        mismatch_rates = np.array([r["mismatch_rate"] for r in condition_results])
        stage1_Ts = np.array([r["stage1_T"] for r in condition_results])

        # 95% Wilson confidence interval for proportions
        n = n_trials
        p_hat = n_protocol_accepted / n
        z = 1.96
        denominator = 1 + z**2 / n
        center = (p_hat + z**2 / (2 * n)) / denominator
        margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denominator

        tables[condition.name] = {
            "n_trials": n_trials,
            "protocol_acceptance_rate": n_protocol_accepted / n_trials,
            "stage1_rejection_rate": 1.0 - (n_stage1_passed / n_trials),
            "mean_mismatch_rate": float(np.mean(mismatch_rates)),
            "std_mismatch_rate": float(np.std(mismatch_rates)),
            "mean_stage1_T": float(np.mean(stage1_Ts)),
            "max_stage1_T": float(np.max(stage1_Ts)),
            "ci_95_protocol_acceptance": (max(0.0, center - margin), min(1.0, center + margin)),
            "condition_description": condition.description,
            "primary_detector": condition.primary_detector,
        }

    return tables


def format_detection_table(tables: dict[str, dict[str, Any]]) -> str:
    """Format detection-rate table as a readable string for reporting."""
    lines = []
    lines.append(f"{'Condition':<30} {'N':>6} {'Prot.Accept':>12} {'Stage1.Reject':>14} {'Mean m':>10} {'Max T':>10}")
    lines.append("-" * 86)
    for name, t in tables.items():
        lines.append(
            f"{name:<30} {t['n_trials']:>6} "
            f"{t['protocol_acceptance_rate']:>12.4f} "
            f"{t['stage1_rejection_rate']:>14.4f} "
            f"{t['mean_mismatch_rate']:>10.6f} "
            f"{t['max_stage1_T']:>10.4f}"
        )
    return "\n".join(lines)
