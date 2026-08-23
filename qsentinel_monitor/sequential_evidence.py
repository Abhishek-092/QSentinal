"""
Phase 6B Sequential Evidence Engine for QSENTINEL.

Pure, deterministic state transition function:
previous_state + decision -> SequentialUpdateResult(previous_state, next_state, outcome, ...)

PERFORMS ZERO DISK IO, ZERO ARTIFACT LOADING, ZERO SEED ALLOCATION, ZERO MONTE CARLO SIMULATION,
AND ZERO QDS PROTOCOL MUTATION.
"""
import math
from typing import Optional, Tuple
from qsentinel_monitor.quantum_evidence.models import (
    CalibratedStage1Decision,
    CalibrationLookupStatus,
    CalibratedDecisionStatus,
)
from qsentinel_monitor.sequential_evidence_models import (
    SequentialEvidenceState,
    SequentialDecisionStatus,
    SessionProcessingOutcome,
    ProvenanceIdentity,
    SequentialUpdateResult,
)


def create_initial_sequential_state() -> SequentialEvidenceState:
    """Creates the initial empty SequentialEvidenceState."""
    return SequentialEvidenceState(
        cumulative_evidence=0.0,
        processed_valid_count=0,
        skipped_session_count=0,
        last_accepted_session_id=None,
        last_accepted_sequence_number=0,
        provenance_identity=None,
        decision_status=SequentialDecisionStatus.SEQUENTIAL_UNINITIALIZED,
        history_session_ids=(),
    )


def update_sequential_evidence(
    previous_state: SequentialEvidenceState,
    decision: CalibratedStage1Decision,
    sequence_number: Optional[int] = None,
    threshold_t_seq: float = 15.0,
) -> SequentialUpdateResult:
    """
    Computes deterministic state transition:
    previous_state + decision -> next_state
    
    Mathematically:
    evidence_delta = T_session - c_alpha(p_matched) if EXACT_MATCH
                   = 0.0 otherwise
    """
    session_id = decision.session_id

    # Defensive state invariant checks
    if previous_state.processed_valid_count < 0 or previous_state.skipped_session_count < 0:
        raise ValueError("Corrupted previous sequential state: negative session count.")
    if math.isnan(previous_state.cumulative_evidence) or math.isinf(previous_state.cumulative_evidence):
        raise ValueError("Corrupted previous sequential state: non-finite cumulative evidence.")

    # Rule 1: Duplicate session protection
    if session_id in previous_state.history_session_ids:
        return SequentialUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=SessionProcessingOutcome.DUPLICATE_SESSION,
            decision_evaluated=decision,
            evidence_delta=0.0,
            diagnostic_reason=f"Session {session_id} has already been processed in sequence history.",
        )

    # Rule 2: Sequence ordering enforcement
    if sequence_number is not None:
        if sequence_number <= previous_state.last_accepted_sequence_number:
            return SequentialUpdateResult(
                previous_state=previous_state,
                next_state=previous_state,
                outcome=SessionProcessingOutcome.OUT_OF_ORDER_SESSION,
                decision_evaluated=decision,
                evidence_delta=0.0,
                diagnostic_reason=f"Sequence number {sequence_number} is out-of-order (last accepted: {previous_state.last_accepted_sequence_number}).",
            )
        next_seq_num = sequence_number
    else:
        next_seq_num = previous_state.last_accepted_sequence_number + 1

    # Rule 3: Provenance compatibility check
    current_prov = ProvenanceIdentity(
        artifact_content_hash=decision.artifact_content_hash,
        artifact_schema_version=decision.artifact_schema_version,
        architecture_version=decision.architecture_version,
        stage1_model_version=decision.stage1_model_version,
    )

    if previous_state.provenance_identity is not None:
        if previous_state.provenance_identity != current_prov:
            return SequentialUpdateResult(
                previous_state=previous_state,
                next_state=previous_state,
                outcome=SessionProcessingOutcome.INCOMPATIBLE_PROVENANCE,
                decision_evaluated=decision,
                evidence_delta=0.0,
                diagnostic_reason="Incoming decision has incompatible calibration artifact provenance.",
            )
    target_provenance = previous_state.provenance_identity or current_prov

    # Rule 4: Non-contributing inputs / skip checks
    if decision.lookup_status == CalibrationLookupStatus.STAGE1_UNAVAILABLE:
        next_state = SequentialEvidenceState(
            cumulative_evidence=previous_state.cumulative_evidence,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity,
            decision_status=previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
        )
        return SequentialUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=SessionProcessingOutcome.UNAVAILABLE_STAGE1,
            decision_evaluated=decision,
            evidence_delta=0.0,
            diagnostic_reason="Stage 1 unavailable for session.",
        )

    if decision.lookup_status in (
        CalibrationLookupStatus.CALIBRATION_UNAVAILABLE,
        CalibrationLookupStatus.CALIBRATION_OUT_OF_SUPPORT,
    ):
        next_state = SequentialEvidenceState(
            cumulative_evidence=previous_state.cumulative_evidence,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity,
            decision_status=previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
        )
        return SequentialUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=SessionProcessingOutcome.UNAVAILABLE_CALIBRATION,
            decision_evaluated=decision,
            evidence_delta=0.0,
            diagnostic_reason=f"Calibration unavailable or out of support ({decision.lookup_status.value}).",
        )

    if decision.lookup_status == CalibrationLookupStatus.DEGENERATE_BOUNDARY:
        next_state = SequentialEvidenceState(
            cumulative_evidence=previous_state.cumulative_evidence,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity,
            decision_status=previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
        )
        return SequentialUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=SessionProcessingOutcome.UNAVAILABLE_CALIBRATION,
            decision_evaluated=decision,
            evidence_delta=0.0,
            diagnostic_reason="Degenerate p=0 boundary null produces zero regular evidence contribution.",
        )

    # Rule 5: Numerical validation
    raw_T = decision.raw_statistic_t
    crit_val = decision.empirical_critical_value

    if (
        math.isnan(raw_T)
        or math.isinf(raw_T)
        or crit_val is None
        or math.isnan(crit_val)
        or math.isinf(crit_val)
    ):
        next_state = SequentialEvidenceState(
            cumulative_evidence=previous_state.cumulative_evidence,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity,
            decision_status=previous_state.decision_status,
            history_session_ids=previous_state.history_session_ids,
        )
        return SequentialUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=SessionProcessingOutcome.INVALID_NUMERICAL_INPUT,
            decision_evaluated=decision,
            evidence_delta=0.0,
            diagnostic_reason="Non-finite raw T or critical value.",
        )

    # Rule 6: Valid Evidence Accumulation
    # Formula: delta = T_session - c_alpha(p_matched)
    evidence_delta = float(raw_T - crit_val)
    new_cum_evidence = float(previous_state.cumulative_evidence + evidence_delta)

    new_decision_status = (
        SequentialDecisionStatus.SEQUENTIAL_EVIDENCE_ELEVATED
        if new_cum_evidence > threshold_t_seq
        else SequentialDecisionStatus.SEQUENTIAL_NOMINAL
    )

    new_history = previous_state.history_session_ids + (session_id,)

    next_state = SequentialEvidenceState(
        cumulative_evidence=new_cum_evidence,
        processed_valid_count=previous_state.processed_valid_count + 1,
        skipped_session_count=previous_state.skipped_session_count,
        last_accepted_session_id=session_id,
        last_accepted_sequence_number=next_seq_num,
        provenance_identity=target_provenance,
        decision_status=new_decision_status,
        history_session_ids=new_history,
    )

    return SequentialUpdateResult(
        previous_state=previous_state,
        next_state=next_state,
        outcome=SessionProcessingOutcome.EVIDENCE_ACCEPTED,
        decision_evaluated=decision,
        evidence_delta=evidence_delta,
        diagnostic_reason=f"Evidence accepted (delta={evidence_delta:.4f}, total={new_cum_evidence:.4f}).",
    )
