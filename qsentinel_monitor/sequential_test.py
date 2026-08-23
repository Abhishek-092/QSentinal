"""
Stage 2 Joint Sequential Likelihood Test Engine for QSENTINEL.

Computes exact session log-likelihood evidence for H0 (symmetric noise q_Z = q_X = 2p/3)
vs H1 (asymmetric basis-specific noise q_Z != q_X) using scipy.special.gammaln.

Accumulates sequential generalized likelihood ratio (GLR) evidence deterministically.
PERFORMS ZERO MONTE CARLO, ZERO SEED ALLOCATION, ZERO SIMULATION, AND MUTATES NO PROTOCOL DATA.
"""
import math
from typing import Optional, Tuple, Union
from scipy.special import gammaln

from qsentinel_monitor.quantum_evidence.models import QuantumEvidence, Stage1Result, CalibratedStage1Decision
from qsentinel_monitor.sequential_test_models import (
    Stage2DecisionStatus,
    Stage2ProcessingOutcome,
    Stage2ProvenanceIdentity,
    SequentialTestState,
    SequentialTestUpdateResult,
)


def _log_binomial_pmf(k: int, n: int, q: float) -> float:
    """
    Numerically stable log Binomial PMF: log Binomial(k | n, q).
    Uses gammaln for log(n! / (k! * (n - k)!)).
    Handles boundaries: k=0, k=n, q=0, q=1 with 0*log(0) = 0 convention.
    """
    if n <= 0:
        return 0.0
    if k < 0 or k > n:
        return -math.inf
    if q < 0.0 or q > 1.0:
        return -math.inf

    # Log combinations: log(n choose k) = gammaln(n+1) - gammaln(k+1) - gammaln(n-k+1)
    log_comb = gammaln(n + 1) - gammaln(k + 1) - gammaln(n - k + 1)

    # q^k term handling
    if k == 0:
        log_q_k = 0.0
    elif q == 0.0:
        return -math.inf
    else:
        log_q_k = k * math.log(q)

    # (1-q)^(n-k) term handling
    n_minus_k = n - k
    if n_minus_k == 0:
        log_1_minus_q = 0.0
    elif q == 1.0:
        return -math.inf
    else:
        log_1_minus_q = n_minus_k * math.log(1.0 - q)

    return log_comb + log_q_k + log_1_minus_q


def compute_session_log_likelihood_ratio(evidence: QuantumEvidence) -> float:
    """
    Computes exact session-level log-likelihood ratio log_lambda = ell_1 - ell_0.
    
    H0: q_Z = q_X = q_hat = (k_Z + k_X) / (n_Z + n_X)
    H1: q_Z_hat = k_Z / n_Z, q_X_hat = k_X / n_X

    ell_0 = log Binomial(k_Z | n_Z, q_hat) + log Binomial(k_X | n_X, q_hat)
    ell_1 = log Binomial(k_Z | n_Z, q_Z_hat) + log Binomial(k_X | n_X, q_X_hat)
    
    log_lambda = ell_1 - ell_0
    """
    k_Z = evidence.z_mismatch_count
    n_Z = evidence.z_sifted_count
    k_X = evidence.x_mismatch_count
    n_X = evidence.x_sifted_count

    if n_Z <= 0 or n_X <= 0:
        raise ValueError(f"Invalid sifted count: n_Z={n_Z}, n_X={n_X}. Sifted counts must be > 0.")

    if k_Z < 0 or k_Z > n_Z or k_X < 0 or k_X > n_X:
        raise ValueError(f"Invalid mismatch bounds: k_Z={k_Z}/{n_Z}, k_X={k_X}/{n_X}.")

    # Unrestricted H1 MLE estimates
    q_Z_hat = k_Z / n_Z
    q_X_hat = k_X / n_X

    # Restricted H0 joint MLE estimate
    q_hat = (k_Z + k_X) / (n_Z + n_X)

    # Log-likelihood under H0
    ell_0_Z = _log_binomial_pmf(k_Z, n_Z, q_hat)
    ell_0_X = _log_binomial_pmf(k_X, n_X, q_hat)
    ell_0 = ell_0_Z + ell_0_X

    # Log-likelihood under H1
    ell_1_Z = _log_binomial_pmf(k_Z, n_Z, q_Z_hat)
    ell_1_X = _log_binomial_pmf(k_X, n_X, q_X_hat)
    ell_1 = ell_1_Z + ell_1_X

    log_lambda = ell_1 - ell_0

    # Guarantee non-negativity within floating point precision (ell_1 >= ell_0 by MLE construction)
    if math.isnan(log_lambda) or math.isinf(log_lambda):
        raise ValueError(f"Non-finite log-likelihood ratio calculated: log_lambda={log_lambda}")

    return max(0.0, float(log_lambda))


def create_initial_stage2_state() -> SequentialTestState:
    """Creates initial empty Stage 2 sequential test state."""
    return SequentialTestState(
        cumulative_log_likelihood_ratio=0.0,
        processed_valid_count=0,
        skipped_session_count=0,
        last_accepted_session_id=None,
        last_accepted_sequence_number=0,
        provenance_identity=None,
        decision_status=Stage2DecisionStatus.STAGE2_UNINITIALIZED,
        history_session_ids=(),
    )


def update_stage2_sequential_test(
    previous_state: SequentialTestState,
    evidence: QuantumEvidence,
    stage1_result: Stage1Result,
    sequence_number: int,
    provenance: Stage2ProvenanceIdentity,
    threshold: Optional[float] = None,
) -> SequentialTestUpdateResult:
    """
    Applies Stage 2 sequential GLR evidence update for a session.
    
    Arguments:
        previous_state: Immutable previous SequentialTestState.
        evidence: QuantumEvidence from session.
        stage1_result: Stage1Result from session.
        sequence_number: Strictly monotonic sequence integer (1, 2, ...).
        provenance: Expected Stage2ProvenanceIdentity.
        threshold: Optional caller-supplied decision threshold (provisional).
    """
    session_id = evidence.session_id

    # Rule 1: Validate session ID uniqueness (duplicate check)
    if session_id in previous_state.history_session_ids or session_id == previous_state.last_accepted_session_id:
        return SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=Stage2ProcessingOutcome.DUPLICATE_SESSION,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_threshold=threshold,
            diagnostic_reason=f"Duplicate session ID '{session_id}' rejected. State unmutated.",
        )

    # Rule 2: Validate sequence order (strictly increasing sequence_number)
    if sequence_number <= previous_state.last_accepted_sequence_number:
        return SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=Stage2ProcessingOutcome.OUT_OF_ORDER_SESSION,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_threshold=threshold,
            diagnostic_reason=f"Out-of-order sequence number {sequence_number} <= {previous_state.last_accepted_sequence_number}. State unmutated.",
        )

    # Rule 3: Validate provenance consistency
    if previous_state.provenance_identity is not None:
        if previous_state.provenance_identity != provenance:
            return SequentialTestUpdateResult(
                previous_state=previous_state,
                next_state=previous_state,
                outcome=Stage2ProcessingOutcome.INCOMPATIBLE_PROVENANCE,
                session_id=session_id,
                sequence_number=sequence_number,
                session_log_likelihood_ratio=0.0,
                applied_threshold=threshold,
                diagnostic_reason=f"Incompatible provenance identity. Expected {previous_state.provenance_identity}, got {provenance}. State unmutated.",
            )

    # Rule 4: Validate Stage 1 processing availability & numerical sanity
    if (
        stage1_result.status != "PROCESSED"
        or not stage1_result.optimization_success
        or math.isnan(stage1_result.statistic)
        or math.isinf(stage1_result.statistic)
        or math.isnan(stage1_result.best_fit_p)
        or math.isinf(stage1_result.best_fit_p)
    ):
        next_state = SequentialTestState(
            cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or provenance,
            decision_status=Stage2DecisionStatus.STAGE2_UNAVAILABLE if previous_state.decision_status == Stage2DecisionStatus.STAGE2_UNINITIALIZED else previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
        )
        return SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=Stage2ProcessingOutcome.UNAVAILABLE_INPUT,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_threshold=threshold,
            diagnostic_reason="Stage 1 processing unavailable or non-finite. Evidence skipped.",
        )

    # Rule 5: Validate basis telemetry bounds
    k_Z = evidence.z_mismatch_count
    n_Z = evidence.z_sifted_count
    k_X = evidence.x_mismatch_count
    n_X = evidence.x_sifted_count

    if (
        n_Z <= 0
        or n_X <= 0
        or k_Z < 0
        or k_Z > n_Z
        or k_X < 0
        or k_X > n_X
        or math.isnan(evidence.z_mismatch_rate)
        or math.isinf(evidence.z_mismatch_rate)
        or math.isnan(evidence.x_mismatch_rate)
        or math.isinf(evidence.x_mismatch_rate)
    ):
        next_state = SequentialTestState(
            cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or provenance,
            decision_status=Stage2DecisionStatus.STAGE2_UNAVAILABLE if previous_state.decision_status == Stage2DecisionStatus.STAGE2_UNINITIALIZED else previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
        )
        return SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=Stage2ProcessingOutcome.INVALID_NUMERICAL_INPUT,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_threshold=threshold,
            diagnostic_reason=f"Invalid telemetry bounds: n_Z={n_Z}, n_X={n_X}, k_Z={k_Z}, k_X={k_X}. Evidence skipped.",
        )

    # Compute exact session GLR log-likelihood ratio log_lambda
    try:
        session_log_lambda = compute_session_log_likelihood_ratio(evidence)
    except ValueError as err:
        next_state = SequentialTestState(
            cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or provenance,
            decision_status=previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
        )
        return SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=Stage2ProcessingOutcome.INVALID_NUMERICAL_INPUT,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_threshold=threshold,
            diagnostic_reason=f"Likelihood computation error: {err}. Evidence skipped.",
        )

    # Accumulate evidence
    new_cumulative = previous_state.cumulative_log_likelihood_ratio + session_log_lambda
    new_valid_count = previous_state.processed_valid_count + 1
    new_history = previous_state.history_session_ids + (session_id,)

    # Evaluate decision status against threshold (provisional caller-supplied threshold)
    if threshold is not None and new_cumulative >= threshold:
        decision_status = Stage2DecisionStatus.STAGE2_EVIDENCE_ELEVATED
    else:
        decision_status = Stage2DecisionStatus.STAGE2_NOMINAL

    next_state = SequentialTestState(
        cumulative_log_likelihood_ratio=new_cumulative,
        processed_valid_count=new_valid_count,
        skipped_session_count=previous_state.skipped_session_count,
        last_accepted_session_id=session_id,
        last_accepted_sequence_number=sequence_number,
        provenance_identity=previous_state.provenance_identity or provenance,
        decision_status=decision_status,
        history_session_ids=new_history,
    )

    return SequentialTestUpdateResult(
        previous_state=previous_state,
        next_state=next_state,
        outcome=Stage2ProcessingOutcome.EVIDENCE_ACCEPTED,
        session_id=session_id,
        sequence_number=sequence_number,
        session_log_likelihood_ratio=session_log_lambda,
        applied_threshold=threshold,
        diagnostic_reason=f"Accepted evidence delta {session_log_lambda:.6f}. Cumulative GLR {new_cumulative:.6f}.",
    )
