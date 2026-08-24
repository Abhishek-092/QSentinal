"""
Pure Runtime Calibrated Stage 2 Decision Engine for QSENTINEL (Phase 6D).

Evaluates Stage 2 sequential state updates against a pre-loaded, verified Stage2CalibrationArtifact.
Enforces fixed stream calibration operating point (calibration_p) and horizon bounds (processed_valid_count <= H).
PERFORMS ZERO DISK IO, ZERO ARTIFACT LOADING, ZERO SEED ALLOCATION, ZERO MONTE CARLO SIMULATION,
AND ZERO RND/QDS PROTOCOL CALLS.
"""

from qsentinel_monitor.stage2_calibration_loader import Stage2CalibrationArtifact
from qsentinel_monitor.quantum_evidence.models import Stage1Result, QuantumEvidence
from qsentinel_monitor.sequential_test import update_stage2_sequential_test
from qsentinel_monitor.sequential_test_models import (
    Stage2DecisionStatus,
    Stage2ProcessingOutcome,
    Stage2ProvenanceIdentity,
    StreamCalibrationContext,
    SequentialTestState,
    SequentialTestUpdateResult,
    CalibratedStage2Decision,
)


def evaluate_calibrated_stage2(
    previous_state: SequentialTestState,
    evidence: QuantumEvidence,
    stage1_result: Stage1Result,
    sequence_number: int,
    calibration_p: float,
    artifact: Stage2CalibrationArtifact,
    tolerance: float = 1e-4,
) -> tuple[SequentialTestUpdateResult, CalibratedStage2Decision]:
    """
    Evaluates Stage 2 sequential evidence update using pre-loaded Stage2CalibrationArtifact.
    Enforces stream operating point calibration_p, horizon bounds, exact p-grid lookup, and provenance.
    Returns tuple of (SequentialTestUpdateResult, CalibratedStage2Decision).
    """
    session_id = evidence.session_id
    horizon_sessions = artifact.calibration_configuration["horizon_sessions"]
    prov_identity = Stage2ProvenanceIdentity(
        artifact_content_hash=artifact.content_hash,
        artifact_schema_version=artifact.schema_version,
        architecture_version=artifact.architecture_version,
        stage1_model_version="v1.0",
        stage2_model_version=artifact.stage2_model_version,
    )

    # Step 1: Validate or freeze stream calibration context
    if previous_state.calibration_context is not None:
        ctx = previous_state.calibration_context
        if ctx.artifact_content_hash != artifact.content_hash:
            # Provenance mismatch
            update_res = update_stage2_sequential_test(
                previous_state, evidence, stage1_result, sequence_number, prov_identity
            )
            calib_dec = CalibratedStage2Decision(
                session_id=session_id,
                sequence_number=sequence_number,
                cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
                processed_valid_count=previous_state.processed_valid_count,
                calibration_p=calibration_p,
                matched_calibration_p=None,
                empirical_critical_value=None,
                horizon_sessions=horizon_sessions,
                decision_status=Stage2DecisionStatus.STAGE2_PROVENANCE_MISMATCH,
                outcome=Stage2ProcessingOutcome.INCOMPATIBLE_PROVENANCE,
                artifact_content_hash=artifact.content_hash,
                artifact_schema_version=artifact.schema_version,
                architecture_version=artifact.architecture_version,
                stage2_model_version=artifact.stage2_model_version,
                calibration_guarantee="HORIZON_BOUNDED",
                diagnostic_reason=f"Stream artifact mismatch. Expected {ctx.artifact_content_hash}, got {artifact.content_hash}.",
            )
            return update_res, calib_dec

        if abs(ctx.calibration_p - calibration_p) > tolerance:
            # Attempted mid-stream calibration operating point change
            calib_dec = CalibratedStage2Decision(
                session_id=session_id,
                sequence_number=sequence_number,
                cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
                processed_valid_count=previous_state.processed_valid_count,
                calibration_p=calibration_p,
                matched_calibration_p=None,
                empirical_critical_value=None,
                horizon_sessions=horizon_sessions,
                decision_status=Stage2DecisionStatus.STAGE2_CALIBRATION_UNAVAILABLE,
                outcome=Stage2ProcessingOutcome.CALIBRATION_UNAVAILABLE,
                artifact_content_hash=artifact.content_hash,
                artifact_schema_version=artifact.schema_version,
                architecture_version=artifact.architecture_version,
                stage2_model_version=artifact.stage2_model_version,
                calibration_guarantee="HORIZON_BOUNDED",
                diagnostic_reason=f"Cannot alter frozen stream calibration_p from {ctx.calibration_p} to {calibration_p}.",
            )
            update_res = SequentialTestUpdateResult(
                previous_state=previous_state,
                next_state=previous_state,
                outcome=Stage2ProcessingOutcome.CALIBRATION_UNAVAILABLE,
                session_id=session_id,
                sequence_number=sequence_number,
                session_log_likelihood_ratio=0.0,
                applied_threshold=None,
                diagnostic_reason=calib_dec.diagnostic_reason,
            )
            return update_res, calib_dec

    # Step 2: Check p-grid matching in artifact
    table = artifact.calibration_table
    p_values = [float(entry["p"]) for entry in table]
    p_min = min(p_values)
    p_max = max(p_values)

    matching_entries = [entry for entry in table if abs(float(entry["p"]) - calibration_p) <= tolerance]

    if not matching_entries:
        out_status = (
            Stage2DecisionStatus.STAGE2_OUT_OF_SUPPORT
            if (calibration_p < p_min - tolerance or calibration_p > p_max + tolerance)
            else Stage2DecisionStatus.STAGE2_CALIBRATION_UNAVAILABLE
        )
        out_enum = (
            Stage2ProcessingOutcome.OUT_OF_SUPPORT
            if out_status == Stage2DecisionStatus.STAGE2_OUT_OF_SUPPORT
            else Stage2ProcessingOutcome.CALIBRATION_UNAVAILABLE
        )
        diag = f"Operating calibration_p {calibration_p} outside calibrated support [{p_min}, {p_max}]." if out_status == Stage2DecisionStatus.STAGE2_OUT_OF_SUPPORT else f"Operating calibration_p {calibration_p} between grid points. Interpolation forbidden."
        
        calib_dec = CalibratedStage2Decision(
            session_id=session_id,
            sequence_number=sequence_number,
            cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
            processed_valid_count=previous_state.processed_valid_count,
            calibration_p=calibration_p,
            matched_calibration_p=None,
            empirical_critical_value=None,
            horizon_sessions=horizon_sessions,
            decision_status=out_status,
            outcome=out_enum,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            stage2_model_version=artifact.stage2_model_version,
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason=diag,
        )
        update_res = SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=out_enum,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_threshold=None,
            diagnostic_reason=diag,
        )
        return update_res, calib_dec

    matched_entry = min(matching_entries, key=lambda e: abs(float(e["p"]) - calibration_p))
    matched_p = float(matched_entry["p"])
    emp_crit_val = float(matched_entry["empirical_critical_value"])

    # Step 3: Check Horizon Limit H
    if previous_state.processed_valid_count >= horizon_sessions:
        calib_dec = CalibratedStage2Decision(
            session_id=session_id,
            sequence_number=sequence_number,
            cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
            processed_valid_count=previous_state.processed_valid_count,
            calibration_p=calibration_p,
            matched_calibration_p=matched_p,
            empirical_critical_value=emp_crit_val,
            horizon_sessions=horizon_sessions,
            decision_status=Stage2DecisionStatus.STAGE2_HORIZON_EXCEEDED,
            outcome=Stage2ProcessingOutcome.HORIZON_EXCEEDED,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            stage2_model_version=artifact.stage2_model_version,
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason=f"Processed valid count {previous_state.processed_valid_count} reached horizon limit {horizon_sessions}. Calibrated false-alarm guarantee expired.",
        )
        next_state = SequentialTestState(
            cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or prov_identity,
            decision_status=Stage2DecisionStatus.STAGE2_HORIZON_EXCEEDED,
            history_session_ids=previous_state.history_session_ids,
            calibration_context=previous_state.calibration_context,
        )
        update_res = SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=Stage2ProcessingOutcome.HORIZON_EXCEEDED,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_threshold=emp_crit_val,
            diagnostic_reason=calib_dec.diagnostic_reason,
        )
        return update_res, calib_dec

    # Initialize calibration context on state if not present
    current_context = previous_state.calibration_context or StreamCalibrationContext(
        calibration_p=calibration_p,
        horizon_sessions=horizon_sessions,
        artifact_content_hash=artifact.content_hash,
        calibration_guarantee="HORIZON_BOUNDED",
    )

    state_with_ctx = SequentialTestState(
        cumulative_log_likelihood_ratio=previous_state.cumulative_log_likelihood_ratio,
        processed_valid_count=previous_state.processed_valid_count,
        skipped_session_count=previous_state.skipped_session_count,
        last_accepted_session_id=previous_state.last_accepted_session_id,
        last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
        provenance_identity=previous_state.provenance_identity or prov_identity,
        decision_status=previous_state.decision_status,
        history_session_ids=previous_state.history_session_ids,
        calibration_context=current_context,
    )

    # Step 4: Execute underlying Stage 2 sequential update with artifact threshold
    update_res = update_stage2_sequential_test(
        state_with_ctx,
        evidence,
        stage1_result,
        sequence_number,
        prov_identity,
        threshold=emp_crit_val,
    )

    if update_res.outcome == Stage2ProcessingOutcome.EVIDENCE_ACCEPTED:
        is_elevated = update_res.next_state.cumulative_log_likelihood_ratio >= emp_crit_val
        dec_status = (
            Stage2DecisionStatus.STAGE2_CALIBRATED_ELEVATED
            if is_elevated
            else Stage2DecisionStatus.STAGE2_CALIBRATED_NOMINAL
        )
        # Update decision_status on next_state
        final_next_state = SequentialTestState(
            cumulative_log_likelihood_ratio=update_res.next_state.cumulative_log_likelihood_ratio,
            processed_valid_count=update_res.next_state.processed_valid_count,
            skipped_session_count=update_res.next_state.skipped_session_count,
            last_accepted_session_id=update_res.next_state.last_accepted_session_id,
            last_accepted_sequence_number=update_res.next_state.last_accepted_sequence_number,
            provenance_identity=update_res.next_state.provenance_identity,
            decision_status=dec_status,
            history_session_ids=update_res.next_state.history_session_ids,
            calibration_context=current_context,
        )
        final_update_res = SequentialTestUpdateResult(
            previous_state=previous_state,
            next_state=final_next_state,
            outcome=update_res.outcome,
            session_id=update_res.session_id,
            sequence_number=update_res.sequence_number,
            session_log_likelihood_ratio=update_res.session_log_likelihood_ratio,
            applied_threshold=emp_crit_val,
            diagnostic_reason=update_res.diagnostic_reason,
        )
        calib_dec = CalibratedStage2Decision(
            session_id=session_id,
            sequence_number=sequence_number,
            cumulative_log_likelihood_ratio=final_next_state.cumulative_log_likelihood_ratio,
            processed_valid_count=final_next_state.processed_valid_count,
            calibration_p=calibration_p,
            matched_calibration_p=matched_p,
            empirical_critical_value=emp_crit_val,
            horizon_sessions=horizon_sessions,
            decision_status=dec_status,
            outcome=Stage2ProcessingOutcome.EVIDENCE_ACCEPTED,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            stage2_model_version=artifact.stage2_model_version,
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason=f"Accepted evidence delta {final_update_res.session_log_likelihood_ratio:.6f}. Cumulative GLR {final_next_state.cumulative_log_likelihood_ratio:.6f} vs threshold {emp_crit_val:.6f}.",
        )
        return final_update_res, calib_dec

    # Other outcomes (e.g. duplicate, out-of-order, unavailable)
    calib_dec = CalibratedStage2Decision(
        session_id=session_id,
        sequence_number=sequence_number,
        cumulative_log_likelihood_ratio=update_res.next_state.cumulative_log_likelihood_ratio,
        processed_valid_count=update_res.next_state.processed_valid_count,
        calibration_p=calibration_p,
        matched_calibration_p=matched_p,
        empirical_critical_value=emp_crit_val,
        horizon_sessions=horizon_sessions,
        decision_status=previous_state.decision_status,
        outcome=update_res.outcome,
        artifact_content_hash=artifact.content_hash,
        artifact_schema_version=artifact.schema_version,
        architecture_version=artifact.architecture_version,
        stage2_model_version=artifact.stage2_model_version,
        calibration_guarantee="HORIZON_BOUNDED",
        diagnostic_reason=update_res.diagnostic_reason,
    )
    return update_res, calib_dec
