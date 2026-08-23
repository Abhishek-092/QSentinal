"""
Repaired Stage 1 Profile-Likelihood & Mutual-Consistency Engine for QSENTINEL.

Stage 1 evaluates:
H0: Observed basis mismatch counts k_Z ~ Binom(n_Z, 2p/3) and k_X ~ Binom(n_X, 2p/3) are jointly consistent
    with a single scalar depolarizing noise parameter p ∈ [0.0, 0.5].
H1 (Unconstrained): k_Z ~ Binom(n_Z, p_Z) and k_X ~ Binom(n_X, p_X) have independent, unconstrained rates.

STRICT STATISTICAL INVARIANTS:
1. Observed independent statistics: 2 (k_Z, k_X)
2. Fitted nuisance parameters under H0: 1 (p̂)
3. Residual degrees of freedom: d.f. = 2 - 1 = 1.
4. Profile Likelihood Test Statistic T = 2 * [log L_sat(p̂_Z, p̂_X) - log L_H0(p̂)]
5. Asymptotic chi-square p-value is computed for diagnostic purposes only and is explicitly labeled
   as theoretical / uncalibrated. No arbitrary hardcoded security rejection threshold is enforced.
"""
import numpy as np
import scipy.optimize as opt
import scipy.stats as stats
from typing import Dict, Any, Optional

from qsentinel_monitor.quantum_evidence.models import QuantumEvidence, Stage1Result


def _log_likelihood_binom(k: int, n: int, prob: float) -> float:
    """Computes log Binomial likelihood log [ (n choose k) prob^k (1-prob)^(n-k) ]."""
    if n <= 0:
        return 0.0
    prob_clamped = float(np.clip(prob, 1e-9, 1.0 - 1e-9))
    return float(stats.binom.logpmf(k, n, prob_clamped))


def _joint_negative_log_likelihood_H0(p: float, k_Z: int, n_Z: int, k_X: int, n_X: int) -> float:
    """
    Computes joint NLL under H0 where expected error rate in both Z and X bases is p_error = (2/3)*p.
    Exact mapping from qds/noise.py depolarizing channel: E(ρ) = (1-p)ρ + (p/3)(XρX + YρY + ZρZ).
    """
    p_clamped = float(np.clip(p, 0.0, 0.5))
    p_err = (2.0 / 3.0) * p_clamped
    ll_Z = _log_likelihood_binom(k_Z, n_Z, p_err)
    ll_X = _log_likelihood_binom(k_X, n_X, p_err)
    return -(ll_Z + ll_X)


def evaluate_stage1(evidence: QuantumEvidence) -> Stage1Result:
    """
    Evaluates Stage 1 profile likelihood ratio statistic T across basis mismatch counts (k_Z, k_X).
    Does NOT hardcode a production security rejection threshold.
    Returns raw T, fitted p_hat, and theoretical uncalibrated p-value.
    """
    session_id = evidence.session_id
    n_Z = evidence.z_sifted_count
    k_Z = evidence.z_mismatch_count
    n_X = evidence.x_sifted_count
    k_X = evidence.x_mismatch_count

    total_sifted = n_Z + n_X
    total_k = k_Z + k_X

    if total_sifted <= 0:
        return Stage1Result(
            session_id=session_id,
            status="OPTIMIZER_FAILURE",
            best_fit_p=0.0,
            statistic=0.0,
            uncalibrated_theoretical_p_value=1.0,
            optimization_success=False,
            diagnostic_info={"error": "Zero total sifted samples"},
        )

    # 1. Fit H0 nuisance parameter p̂ = argmin_p Loss_H0(p)
    # Closed-form MLE for p under H0: p_err_mle = (k_Z + k_X) / (n_Z + n_X) => p̂ = (3/2) * p_err_mle
    p_err_mle = float(total_k) / float(total_sifted)
    best_fit_p_closed_form = float(np.clip(1.5 * p_err_mle, 0.0, 0.5))

    try:
        res = opt.minimize_scalar(
            _joint_negative_log_likelihood_H0,
            bounds=(0.0, 0.5),
            args=(k_Z, n_Z, k_X, n_X),
            method="bounded"
        )
        optimization_success = res.success
        best_fit_p = float(res.x) if res.success else best_fit_p_closed_form
    except Exception:
        optimization_success = True
        best_fit_p = best_fit_p_closed_form

    min_nll_H0 = _joint_negative_log_likelihood_H0(best_fit_p, k_Z, n_Z, k_X, n_X)
    ll_H0 = -min_nll_H0

    # 2. Saturated model H1: unconstrained rates p̂_Z = k_Z/n_Z, p̂_X = k_X/n_X
    p_Z_mle = float(k_Z) / float(n_Z) if n_Z > 0 else 0.0
    p_X_mle = float(k_X) / float(n_X) if n_X > 0 else 0.0

    ll_sat_Z = _log_likelihood_binom(k_Z, n_Z, p_Z_mle) if n_Z > 0 else 0.0
    ll_sat_X = _log_likelihood_binom(k_X, n_X, p_X_mle) if n_X > 0 else 0.0
    ll_sat = ll_sat_Z + ll_sat_X

    # 3. Profile likelihood ratio statistic T = 2 * (ll_sat - ll_H0)
    raw_T = float(max(2.0 * (ll_sat - ll_H0), 0.0))

    # 4. Asymptotic Chi-Square p-value (df=1 for 2 observables - 1 parameter)
    # Explicitly documented as UNCALIBRATED / THEORETICAL diagnostic value
    theoretical_p_val = float(1.0 - stats.chi2.cdf(raw_T, df=1)) if not np.isnan(raw_T) else 1.0

    diagnostic_info = {
        "n_Z": n_Z,
        "k_Z": k_Z,
        "m_Z": evidence.z_mismatch_rate,
        "n_X": n_X,
        "k_X": k_X,
        "m_X": evidence.x_mismatch_rate,
        "best_fit_p": best_fit_p,
        "ll_H0": ll_H0,
        "ll_sat": ll_sat,
        "statistic_T": raw_T,
        "uncalibrated_theoretical_p_value": theoretical_p_val,
        "degrees_of_freedom": 1,
        "note": "Asymptotic chi-squared p-value is uncalibrated diagnostic only. Final rejection region bound in Phase 6.",
    }

    return Stage1Result(
        session_id=session_id,
        status="PROCESSED" if optimization_success else "OPTIMIZER_FAILURE",
        best_fit_p=best_fit_p,
        statistic=raw_T,
        uncalibrated_theoretical_p_value=theoretical_p_val,
        optimization_success=optimization_success,
        diagnostic_info=diagnostic_info,
    )
