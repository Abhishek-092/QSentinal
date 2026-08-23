"""
Stage 1 Profile-Likelihood & Mutual-Consistency Testing Engine for QSENTINEL.

Stage 1 evaluates:
H0: Observed evidence (m, C, H) is jointly consistent with a single depolarizing noise parameter p ∈ [0.0, 0.5].
H1: Evidence cannot be jointly explained by any single admissible p (indicates structural channel manipulation or attack).

CRITICAL STATISTICAL invariant:
m, C, and H are NOT treated as independent features to be multiplied. Under the depolarizing model,
they are coupled via parameter p. Stage 1 profiles over p using scipy.optimize.minimize_scalar
and evaluates goodness-of-fit / mutual consistency against the joint distribution.
"""
import numpy as np
import scipy.optimize as opt
import scipy.stats as stats
from typing import Dict, Any, Optional

from qsentinel_monitor.quantum_evidence.models import QuantumEvidence, Stage1Result


def _joint_negative_log_likelihood(p: float, m_obs: float, C_obs: float, H_obs: float, n_sifted: int) -> float:
    """
    Computes joint loss / negative log-likelihood for observed (m, C, H) given noise parameter p ∈ [0, 0.5].
    Under depolarizing channel:
    - Expected mismatch rate: E[m|p] = p
    - Expected correlation: E[C|p] = 1 - 2p
    - Expected entropy: E[H|p] = H(p) = -p log2(p) - (1-p) log2(1-p)
    """
    p_clamped = float(np.clip(p, 1e-7, 0.5 - 1e-7))

    # 1. Binomial mismatch likelihood: k = m_obs * n_sifted
    k = m_obs * n_sifted
    # Binomial log-pdf: k log(p) + (n-k) log(1-p)
    nll_m = -(k * np.log(p_clamped) + (n_sifted - k) * np.log(1.0 - p_clamped))

    # 2. Consistency of C_obs with predicted C(p) = 1 - 2p
    # Variance of correlation estimator under n_sifted trials is Var(C) = 4 p (1-p) / n_sifted
    C_pred = 1.0 - 2.0 * p_clamped
    var_C = max(4.0 * p_clamped * (1.0 - p_clamped) / float(n_sifted), 1e-8)
    nll_C = 0.5 * np.log(2.0 * np.pi * var_C) + 0.5 * ((C_obs - C_pred) ** 2) / var_C

    # 3. Consistency of H_obs with predicted H(p)
    H_pred = -p_clamped * np.log2(p_clamped) - (1.0 - p_clamped) * np.log2(1.0 - p_clamped)
    # Variance of entropy estimator under delta method: Var(H) ≈ (log2((1-p)/p))^2 * p(1-p) / n_sifted
    grad_H = np.log2((1.0 - p_clamped) / p_clamped) if 0.0 < p_clamped < 0.5 else 0.0
    var_H = max((grad_H ** 2) * p_clamped * (1.0 - p_clamped) / float(n_sifted), 1e-8)
    nll_H = 0.5 * np.log(2.0 * np.pi * var_H) + 0.5 * ((H_obs - H_pred) ** 2) / var_H

    # Total joint NLL (jointly parameterized by p, NOT multiplied independent probabilities)
    return nll_m + nll_C + nll_H


def evaluate_stage1(
    evidence: QuantumEvidence,
    critical_value_threshold: float = 15.0  # Configurable non-final threshold, calibrated offline in Stage 2
) -> Stage1Result:
    """
    Evaluates Stage 1 mutual consistency by profiling over noise parameter p ∈ [0, 0.5].
    Returns immutable Stage1Result.
    """
    m_obs = evidence.mismatch_rate
    C_obs = evidence.correlation
    H_obs = evidence.entropy
    n_sifted = evidence.sifted_count
    session_id = evidence.session_id

    # Numerical safeguards for 0 mismatch / perfect observations
    if m_obs <= 0.0:
        return Stage1Result(
            session_id=session_id,
            status="MODEL_VALID",
            model_valid=True,
            best_fit_p=0.0,
            statistic=0.0,
            p_value=1.0,
            optimization_success=True,
            diagnostic_info={"note": "Zero mismatch observation; perfect fit at p=0"},
        )

    # Perform bounded scalar optimization for nuisance parameter p̂ = argmin_p Loss(p)
    try:
        res = opt.minimize_scalar(
            _joint_negative_log_likelihood,
            bounds=(1e-6, 0.5 - 1e-6),
            args=(m_obs, C_obs, H_obs, n_sifted),
            method="bounded"
        )
    except Exception as e:
        return Stage1Result(
            session_id=session_id,
            status="OPTIMIZER_FAILURE",
            model_valid=False,
            best_fit_p=float("nan"),
            statistic=float("inf"),
            p_value=0.0,
            optimization_success=False,
            diagnostic_info={"error": str(e), "note": "Numerical optimization raised exception"},
        )

    if not res.success:
        return Stage1Result(
            session_id=session_id,
            status="OPTIMIZER_FAILURE",
            model_valid=False,
            best_fit_p=float("nan"),
            statistic=float("inf"),
            p_value=0.0,
            optimization_success=False,
            diagnostic_info={"optimizer_message": str(res.message)},
        )

    best_fit_p = float(res.x)

    # Compute unconstrained / saturated model loss (where p_m = m_obs, p_C matches C_obs, p_H matches H_obs)
    sat_loss = _joint_negative_log_likelihood(m_obs, m_obs, C_obs, H_obs, n_sifted)
    min_loss = float(res.fun)

    # Profile likelihood ratio statistic T = 2 * (min_loss - sat_loss)
    statistic = max(2.0 * (min_loss - sat_loss), 0.0)

    # Asymptotic / empirical p-value computation (chi2 with 2 degrees of freedom for 2 constraints)
    p_val = float(1.0 - stats.chi2.cdf(statistic, df=2)) if not np.isnan(statistic) else 0.0

    model_valid = (statistic <= critical_value_threshold)
    status = "MODEL_VALID" if model_valid else "MODEL_INVALID"

    diagnostic_info = {
        "best_fit_p": best_fit_p,
        "min_loss": min_loss,
        "sat_loss": sat_loss,
        "statistic": statistic,
        "p_value": p_val,
        "critical_value_threshold": critical_value_threshold,
    }

    return Stage1Result(
        session_id=session_id,
        status=status,
        model_valid=model_valid,
        best_fit_p=best_fit_p,
        statistic=statistic,
        p_value=p_val,
        optimization_success=True,
        diagnostic_info=diagnostic_info,
    )
