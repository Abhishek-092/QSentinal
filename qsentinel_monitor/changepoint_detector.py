"""
Phase 8 Change-Point (Offset GLR-CUSUM) Detector Core Engine for QSENTINEL.

Computes pure deterministic Offset GLR-CUSUM updates:
  C_k = max(0, C_{k-1} + log_lambda_k - d(p))
  active_run_length: incremented when raw_increment > 0, reset to 0 when <= 0
  estimated_excursion_onset = k - active_run_length + 1 when elevated.

PERFORMS ZERO MONTE CARLO, ZERO SEED ALLOCATION, ZERO SIMULATION, ZERO DISK IO, AND MUTATES NO PROTOCOL DATA.
"""
import math
from typing import Optional

from qsentinel_monitor.quantum_evidence.models import QuantumEvidence, Stage1Result
from qsentinel_monitor.sequential_test import compute_session_log_likelihood_ratio
from qsentinel_monitor.changepoint_models import (
    ChangePointDecisionStatus,
    ChangePointProcessingOutcome,
    ChangePointProvenanceIdentity,
    ChangePointTestState,
    ChangePointUpdateResult,
)


def create_initial_changepoint_state() -> ChangePointTestState:
    """Creates initial empty ChangePointTestState."""
    return ChangePointTestState(
        cusum_statistic=0.0,
        active_run_length=0,
        estimated_excursion_onset=None,
        processed_valid_count=0,
        skipped_session_count=0,
        last_accepted_session_id=None,
        last_accepted_sequence_number=0,
        provenance_identity=None,
        decision_status=ChangePointDecisionStatus.CHANGEPOINT_UNINITIALIZED,
        history_session_ids=(),
    )


def update_changepoint_detector(
    previous_state: ChangePointTestState,
    evidence: QuantumEvidence,
    stage1_result: Stage1Result,
    sequence_number: int,
    provenance: ChangePointProvenanceIdentity,
    null_offset_d: Optional[float] = None,
    threshold: Optional[float] = None,
) -> ChangePointUpdateResult:
    """
    Applies Offset GLR-CUSUM change-point detector update for a session.
    
    Arguments:
        previous_state: Immutable previous ChangePointTestState.
        evidence: QuantumEvidence from session.
        stage1_result: Stage1Result from session.
        sequence_number: Strictly monotonic sequence integer (1, 2, ...).
        provenance: Expected ChangePointProvenanceIdentity.
        null_offset_d: Calibrated baseline null drift offset d(p).
        threshold: Optional decision threshold (provisional/calibrated).
    """
    session_id = evidence.session_id

    # Rule 0: Frozen state check if already elevated
    if previous_state.decision_status == ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED:
        return ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=ChangePointProcessingOutcome.EVIDENCE_ACCEPTED,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=null_offset_d,
            applied_threshold=threshold,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason="Detector is frozen in CALIBRATED_ELEVATED state. Requires explicit epoch renewal.",
        )

    # Rule 1: Duplicate session check
    if session_id in previous_state.history_session_ids or session_id == previous_state.last_accepted_session_id:
        return ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=ChangePointProcessingOutcome.DUPLICATE_SESSION,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=null_offset_d,
            applied_threshold=threshold,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason=f"Duplicate session ID '{session_id}' rejected. State unmutated.",
        )

    # Rule 2: Strictly increasing sequence number check
    if sequence_number <= previous_state.last_accepted_sequence_number:
        return ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=ChangePointProcessingOutcome.OUT_OF_ORDER_SESSION,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=null_offset_d,
            applied_threshold=threshold,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason=f"Out-of-order sequence number {sequence_number} <= {previous_state.last_accepted_sequence_number}. State unmutated.",
        )

    # Rule 3: Validate provenance identity consistency
    if previous_state.provenance_identity is not None:
        if previous_state.provenance_identity != provenance:
            return ChangePointUpdateResult(
                previous_state=previous_state,
                next_state=previous_state,
                outcome=ChangePointProcessingOutcome.INCOMPATIBLE_PROVENANCE,
                session_id=session_id,
                sequence_number=sequence_number,
                session_log_likelihood_ratio=0.0,
                applied_null_offset=null_offset_d,
                applied_threshold=threshold,
                active_run_length=previous_state.active_run_length,
                estimated_excursion_onset=previous_state.estimated_excursion_onset,
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
        next_state = ChangePointTestState(
            cusum_statistic=previous_state.cusum_statistic,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or provenance,
            decision_status=ChangePointDecisionStatus.CHANGEPOINT_UNAVAILABLE if previous_state.decision_status == ChangePointDecisionStatus.CHANGEPOINT_UNINITIALIZED else previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
            calibration_context=previous_state.calibration_context,
        )
        return ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=ChangePointProcessingOutcome.UNAVAILABLE_INPUT,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=null_offset_d,
            applied_threshold=threshold,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
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
        next_state = ChangePointTestState(
            cusum_statistic=previous_state.cusum_statistic,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or provenance,
            decision_status=ChangePointDecisionStatus.CHANGEPOINT_UNAVAILABLE if previous_state.decision_status == ChangePointDecisionStatus.CHANGEPOINT_UNINITIALIZED else previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
            calibration_context=previous_state.calibration_context,
        )
        return ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=ChangePointProcessingOutcome.INVALID_NUMERICAL_INPUT,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=null_offset_d,
            applied_threshold=threshold,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason=f"Invalid telemetry bounds: n_Z={n_Z}, n_X={n_X}, k_Z={k_Z}, k_X={k_X}. Evidence skipped.",
        )

    # Compute exact session log-likelihood ratio log_lambda
    try:
        session_log_lambda = compute_session_log_likelihood_ratio(evidence)
    except ValueError as err:
        next_state = ChangePointTestState(
            cusum_statistic=previous_state.cusum_statistic,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or provenance,
            decision_status=previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
            calibration_context=previous_state.calibration_context,
        )
        return ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=ChangePointProcessingOutcome.INVALID_NUMERICAL_INPUT,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=null_offset_d,
            applied_threshold=threshold,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason=f"Likelihood computation error: {err}. Evidence skipped.",
        )

    # Apply Offset CUSUM Recurrence
    d_val = null_offset_d if null_offset_d is not None else 0.0
    raw_increment = previous_state.cusum_statistic + session_log_lambda - d_val
    new_cusum = max(0.0, float(raw_increment))

    if raw_increment > 0.0:
        new_active_run = previous_state.active_run_length + 1
    else:
        new_active_run = 0

    new_valid_count = previous_state.processed_valid_count + 1
    new_history = previous_state.history_session_ids + (session_id,)

    # Evaluate elevation status against threshold
    if threshold is not None and new_cusum >= threshold:
        decision_status = ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED
        estimated_onset = new_valid_count - new_active_run + 1
    else:
        decision_status = ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_NOMINAL
        estimated_onset = None

    next_state = ChangePointTestState(
        cusum_statistic=new_cusum,
        active_run_length=new_active_run,
        estimated_excursion_onset=estimated_onset,
        processed_valid_count=new_valid_count,
        skipped_session_count=previous_state.skipped_session_count,
        last_accepted_session_id=session_id,
        last_accepted_sequence_number=sequence_number,
        provenance_identity=previous_state.provenance_identity or provenance,
        decision_status=decision_status,
        history_session_ids=new_history,
        calibration_context=previous_state.calibration_context,
    )

    return ChangePointUpdateResult(
        previous_state=previous_state,
        next_state=next_state,
        outcome=ChangePointProcessingOutcome.EVIDENCE_ACCEPTED,
        session_id=session_id,
        sequence_number=sequence_number,
        session_log_likelihood_ratio=session_log_lambda,
        applied_null_offset=null_offset_d,
        applied_threshold=threshold,
        active_run_length=new_active_run,
        estimated_excursion_onset=estimated_onset,
        diagnostic_reason=f"Accepted evidence log_lambda={session_log_lambda:.6f}, offset d={d_val:.6f}. CUSUM={new_cusum:.6f}, run_length={new_active_run}.",
    )
