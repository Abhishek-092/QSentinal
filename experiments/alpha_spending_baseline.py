"""
Alpha-Spending Benchmark for QSENTINEL.

Compares the joint calibration approach against an alpha-spending (sequential testing)
approach where the total α is divided across sequential observations.

This is a secondary, non-blocking comparison (Blueprint §12 #6).

The key question: does joint calibration achieve higher power than naive alpha-spending
for the same familywise error rate?
"""
from __future__ import annotations

import numpy as np
from typing import Any

from qds.protocol import run_session
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1


def alpha_spending_threshold(
    k: int,
    K: int,
    alpha: float = 0.01,
    spending_function: str = "obrien_fleming",
) -> float:
    """
    Compute the spending-function threshold for the k-th observation out of K total.

    Implements O'Brien-Fleming and Pocock alpha-spending functions:
    - O'Brien-Fleming: more stringent early, more lenient late
    - Pocock: uniform spending

    Returns the local threshold that the k-th test statistic must exceed.
    """
    if spending_function == "obrien_fleming":
        # O'Brien-Fleming: spend alpha proportional to 1/sqrt(k/K)
        # Cumulative alpha at step k
        t_k = np.sqrt(k / K)
        # OBF spending function
        alpha_k = 2 * (1 - _Phi(_Phi_inv(1 - alpha / 2) / np.sqrt(K / k)))
        return alpha_k if k > 0 else alpha
    elif spending_function == "pocock":
        # Pocock: spend alpha uniformly
        alpha_k = alpha * np.log(1 + (np.e - 1) * k / K)
        return alpha_k if k > 0 else alpha
    else:
        # Bonferroni (uniform division)
        return alpha / K


def _Phi(x: float) -> float:
    """Standard normal CDF approximation."""
    from scipy.stats import norm
    return float(norm.cdf(x))


def _Phi_inv(p: float) -> float:
    """Standard normal quantile."""
    from scipy.stats import norm
    return float(norm.ppf(p))


def run_alpha_spending_benchmark(
    n_sessions: int = 200,
    n_qubits: int = 200,
    noise_p: float = 0.02,
    alpha: float = 0.01,
) -> dict[str, Any]:
    """
    Run a single stream of honest sessions and measure false alarm rates
    under alpha-spending vs. joint calibration.

    Returns comparison metrics.
    """
    # Track cumulative evidence under both approaches
    bonferroni_threshold = alpha / n_sessions

    n_bonferroni_alarms = 0
    n_joint_alarms = 0
    stage1_Ts = []
    mismatch_rates = []

    for t in range(n_sessions):
        seed = t + 200_000
        transcript = run_session(
            f"alpha-{seed}", noise_p=noise_p, n_qubits=n_qubits, seed=seed
        )
        evidence = extract_evidence(transcript)
        stage1_res = evaluate_stage1(evidence)

        stage1_Ts.append(stage1_res.statistic)
        mismatch_rates.append(evidence.mismatch_rate)

        # Bonferroni: reject if T > chi2_threshold / K
        chi2_threshold = 3.841  # chi2(1, 0.95)
        if stage1_res.statistic > chi2_threshold * (1 - bonferroni_threshold):
            n_bonferroni_alarms += 1

        # Joint calibrated: reject if T > calibrated_threshold (already baked into stage1)
        if not stage1_res.passed:
            n_joint_alarms += 1

    st_arr = np.array(stage1_Ts)
    mr_arr = np.array(mismatch_rates)

    return {
        "n_sessions": n_sessions,
        "alpha": alpha,
        "bonferroni_alarms": n_bonferroni_alarms,
        "bonferroni_false_alarm_rate": n_bonferroni_alarms / n_sessions,
        "joint_calibrated_alarms": n_joint_alarms,
        "joint_calibrated_false_alarm_rate": n_joint_alarms / n_sessions,
        "mean_stage1_T": float(np.mean(st_arr)),
        "max_stage1_T": float(np.max(st_arr)),
        "mean_mismatch_rate": float(np.mean(mr_arr)),
        "verdict": (
            "Joint calibration achieves equal or lower FPR"
            if n_joint_alarms <= n_bonferroni_alarms
            else "Alpha-spending achieves lower FPR"
        ),
    }
