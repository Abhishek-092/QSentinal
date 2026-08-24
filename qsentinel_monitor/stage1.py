"""Stage 1: Profile-likelihood mutual-consistency test."""

from __future__ import annotations

import math
from dataclasses import dataclass

from qsentinel_monitor.quantum_evidence.collector import QuantumEvidence


@dataclass(frozen=True)
class Stage1Result:
    p_hat: float
    ll_ratio: float
    passed: bool
    details: str
    optimizer_converged: bool


def _neg_log_likelihood(p: float, m: float, n: int = 100) -> float:
    p = max(1e-9, min(p, 0.4999))
    return -(n * m * math.log(p) + n * (1 - m) * math.log(1 - p))


def _minimize_bounded(func, lo: float, hi: float, steps: int = 500) -> tuple[float, bool]:
    best_x, best_y = lo, func(lo)
    for i in range(steps + 1):
        x = lo + (hi - lo) * i / steps
        y = func(x)
        if y < best_y:
            best_x, best_y = x, y
    return best_x, True


def run_stage1(evidence: QuantumEvidence, n: int = 100) -> Stage1Result:
    """Profile-likelihood test with explicit boundary optima handling."""
    m = evidence.mismatch_rate
    p0 = 0.02

    optimizer_converged = True
    try:
        p_hat, optimizer_converged = _minimize_bounded(
            lambda p: _neg_log_likelihood(p, m, n),
            1e-6,
            0.4999,
        )
    except Exception:
        p_hat = 0.0
        optimizer_converged = False

    ll_h0 = -_neg_log_likelihood(p0, m, n)
    ll_h1 = -_neg_log_likelihood(p_hat, m, n)
    ll_ratio = float(2 * (ll_h1 - ll_h0))

    if p_hat <= 1e-5:
        details = "Boundary optimum at p_hat=0 (honest model)"
        passed = True
    elif p_hat >= 0.499:
        details = "Boundary optimum at p_hat=0.5 (maximal mismatch)"
        passed = False
    elif ll_ratio < 3.84:
        details = f"Mutual consistency satisfied (LR={ll_ratio:.3f})"
        passed = True
    else:
        details = f"Likelihood ratio exceeds chi-sq threshold (LR={ll_ratio:.3f})"
        passed = False

    return Stage1Result(
        p_hat=p_hat,
        ll_ratio=ll_ratio,
        passed=passed,
        details=details,
        optimizer_converged=optimizer_converged,
    )
