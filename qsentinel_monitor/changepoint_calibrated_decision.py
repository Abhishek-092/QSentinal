"""
Pure Runtime Calibrated Change-Point Decision Engine for QSENTINEL (Phase 8).

Evaluates ChangePointTestState updates against a pre-loaded, verified ChangePointCalibrationArtifact.
Enforces fixed stream calibration operating point (calibration_p) and horizon bounds:
  - 1 <= k <= H is calibrated.
  - k > H triggers CHANGEPOINT_HORIZON_EXCEEDED.
  - Frozen state preservation after elevation.

PERFORMS ZERO DISK IO, ZERO ARTIFACT LOADING, ZERO SEED ALLOCATION, ZERO MONTE CARLO SIMULATION,
AND ZERO RND/QDS PROTOCOL CALLS.
"""
from typing import Tuple, Optional, List
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact
from qsentinel_monitor.quantum_evidence.models import Stage1Result, QuantumEvidence
from qsentinel_monitor.changepoint_detector import update_changepoint_detector
from qsentinel_monitor.changepoint_models import (
    ChangePointDecisionStatus,
    ChangePointProcessingOutcome,
    ChangePointProvenanceIdentity,
    StreamChangePointContext,
    ChangePointTestState,
    ChangePointUpdateResult,
    CalibratedChangePointDecision,
)


def evaluate_calibrated_changepoint(
    previous_state: ChangePointTestState,
    evidence: QuantumEvidence,
    stage1_result: Stage1Result,
    sequence_number: int,
    calibration_p: float,
    artifact: ChangePointCalibrationArtifact,
    tolerance: float = 1e-4,
) -> Tuple[ChangePointUpdateResult, CalibratedChangePointDecision]:
    """
    Evaluates session evidence against pre-loaded ChangePointCalibrationArtifact.
    Enforces stream operating point calibration_p, exact p-grid lookup, horizon bounds (k <= H vs k > H),
    frozen elevation preservation, and deep provenance validation.
    """
    session_id = evidence.session_id
    horizon_sessions = artifact.calibration_configuration["horizon_sessions"]
    prov_identity = ChangePointProvenanceIdentity(
        artifact_content_hash=artifact.content_hash,
        artifact_schema_version=artifact.schema_version,
        architecture_version=artifact.architecture_version,
        stage1_model_version="v1.0",
        changepoint_model_version=artifact.changepoint_model_version,
    )

    # Step 0: Check if previous state is already frozen elevated
    if previous_state.decision_status == ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED:
        table_entry = next((e for e in artifact.calibration_table if abs(float(e["p"]) - calibration_p) <= tolerance), None)
        matched_p = float(table_entry["p"]) if table_entry else None
        d_val = float(table_entry["null_offset_d"]) if table_entry else None
        crit_val = float(table_entry["empirical_critical_value"]) if table_entry else None

        calib_dec = CalibratedChangePointDecision(
            session_id=session_id,
            sequence_number=sequence_number,
            cusum_statistic=previous_state.cusum_statistic,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            processed_valid_count=previous_state.processed_valid_count,
            calibration_p=calibration_p,
            matched_calibration_p=matched_p,
            null_offset_d=d_val,
            empirical_critical_value=crit_val,
            horizon_sessions=horizon_sessions,
            decision_status=ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED,
            outcome=ChangePointProcessingOutcome.EVIDENCE_ACCEPTED,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            changepoint_model_version=artifact.changepoint_model_version,
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason="Detector remains frozen in CHANGEPOINT_CALIBRATED_ELEVATED state. Requires stream epoch renewal.",
        )
        update_res = ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=ChangePointProcessingOutcome.EVIDENCE_ACCEPTED,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=d_val,
            applied_threshold=crit_val,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason=calib_dec.diagnostic_reason,
        )
        return update_res, calib_dec

    # Step 1: Validate stream calibration context & provenance consistency
    if previous_state.calibration_context is not None:
        ctx = previous_state.calibration_context
        if ctx.artifact_content_hash != artifact.content_hash:
            update_res = update_changepoint_detector(
                previous_state, evidence, stage1_result, sequence_number, prov_identity
            )
            calib_dec = CalibratedChangePointDecision(
                session_id=session_id,
                sequence_number=sequence_number,
                cusum_statistic=previous_state.cusum_statistic,
                active_run_length=previous_state.active_run_length,
                estimated_excursion_onset=previous_state.estimated_excursion_onset,
                processed_valid_count=previous_state.processed_valid_count,
                calibration_p=calibration_p,
                matched_calibration_p=None,
                null_offset_d=None,
                empirical_critical_value=None,
                horizon_sessions=horizon_sessions,
                decision_status=ChangePointDecisionStatus.CHANGEPOINT_PROVENANCE_MISMATCH,
                outcome=ChangePointProcessingOutcome.INCOMPATIBLE_PROVENANCE,
                artifact_content_hash=artifact.content_hash,
                artifact_schema_version=artifact.schema_version,
                architecture_version=artifact.architecture_version,
                changepoint_model_version=artifact.changepoint_model_version,
                calibration_guarantee="HORIZON_BOUNDED",
                diagnostic_reason=f"Stream artifact mismatch. Expected {ctx.artifact_content_hash}, got {artifact.content_hash}.",
            )
            return update_res, calib_dec

        if abs(ctx.calibration_p - calibration_p) > tolerance:
            calib_dec = CalibratedChangePointDecision(
                session_id=session_id,
                sequence_number=sequence_number,
                cusum_statistic=previous_state.cusum_statistic,
                active_run_length=previous_state.active_run_length,
                estimated_excursion_onset=previous_state.estimated_excursion_onset,
                processed_valid_count=previous_state.processed_valid_count,
                calibration_p=calibration_p,
                matched_calibration_p=None,
                null_offset_d=None,
                empirical_critical_value=None,
                horizon_sessions=horizon_sessions,
                decision_status=ChangePointDecisionStatus.CHANGEPOINT_CALIBRATION_UNAVAILABLE,
                outcome=ChangePointProcessingOutcome.CALIBRATION_UNAVAILABLE,
                artifact_content_hash=artifact.content_hash,
                artifact_schema_version=artifact.schema_version,
                architecture_version=artifact.architecture_version,
                changepoint_model_version=artifact.changepoint_model_version,
                calibration_guarantee="HORIZON_BOUNDED",
                diagnostic_reason=f"Cannot alter frozen stream calibration_p from {ctx.calibration_p} to {calibration_p}.",
            )
            update_res = ChangePointUpdateResult(
                previous_state=previous_state,
                next_state=previous_state,
                outcome=ChangePointProcessingOutcome.CALIBRATION_UNAVAILABLE,
                session_id=session_id,
                sequence_number=sequence_number,
                session_log_likelihood_ratio=0.0,
                applied_null_offset=None,
                applied_threshold=None,
                active_run_length=previous_state.active_run_length,
                estimated_excursion_onset=previous_state.estimated_excursion_onset,
                diagnostic_reason=calib_dec.diagnostic_reason,
            )
            return update_res, calib_dec

    # Step 2: Exact p-grid lookup in calibration table
    table = artifact.calibration_table
    p_values = [float(entry["p"]) for entry in table]
    p_min = min(p_values)
    p_max = max(p_values)

    matching_entries = [entry for entry in table if abs(float(entry["p"]) - calibration_p) <= tolerance]

    if not matching_entries:
        out_status = (
            ChangePointDecisionStatus.CHANGEPOINT_OUT_OF_SUPPORT
            if (calibration_p < p_min - tolerance or calibration_p > p_max + tolerance)
            else ChangePointDecisionStatus.CHANGEPOINT_CALIBRATION_UNAVAILABLE
        )
        out_enum = (
            ChangePointProcessingOutcome.OUT_OF_SUPPORT
            if out_status == ChangePointDecisionStatus.CHANGEPOINT_OUT_OF_SUPPORT
            else ChangePointProcessingOutcome.CALIBRATION_UNAVAILABLE
        )
        diag = (
            f"Operating calibration_p {calibration_p} outside calibrated support [{p_min}, {p_max}]."
            if out_status == ChangePointDecisionStatus.CHANGEPOINT_OUT_OF_SUPPORT
            else f"Operating calibration_p {calibration_p} between grid points. Interpolation forbidden."
        )

        calib_dec = CalibratedChangePointDecision(
            session_id=session_id,
            sequence_number=sequence_number,
            cusum_statistic=previous_state.cusum_statistic,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            processed_valid_count=previous_state.processed_valid_count,
            calibration_p=calibration_p,
            matched_calibration_p=None,
            null_offset_d=None,
            empirical_critical_value=None,
            horizon_sessions=horizon_sessions,
            decision_status=out_status,
            outcome=out_enum,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            changepoint_model_version=artifact.changepoint_model_version,
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason=diag,
        )
        update_res = ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=previous_state,
            outcome=out_enum,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=None,
            applied_threshold=None,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason=diag,
        )
        return update_res, calib_dec

    matched_entry = min(matching_entries, key=lambda e: abs(float(e["p"]) - calibration_p))
    matched_p = float(matched_entry["p"])
    null_offset_d = float(matched_entry["null_offset_d"])
    emp_crit_val = float(matched_entry["empirical_critical_value"])

    # Step 3: Horizon Limit Check (k <= H is valid, k > H is HORIZON_EXCEEDED)
    if previous_state.processed_valid_count >= horizon_sessions:
        calib_dec = CalibratedChangePointDecision(
            session_id=session_id,
            sequence_number=sequence_number,
            cusum_statistic=previous_state.cusum_statistic,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            processed_valid_count=previous_state.processed_valid_count,
            calibration_p=calibration_p,
            matched_calibration_p=matched_p,
            null_offset_d=null_offset_d,
            empirical_critical_value=emp_crit_val,
            horizon_sessions=horizon_sessions,
            decision_status=ChangePointDecisionStatus.CHANGEPOINT_HORIZON_EXCEEDED,
            outcome=ChangePointProcessingOutcome.HORIZON_EXCEEDED,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            changepoint_model_version=artifact.changepoint_model_version,
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason=f"Processed valid count {previous_state.processed_valid_count} exceeds horizon limit {horizon_sessions}. Calibrated false-alarm guarantee expired.",
        )
        next_state = ChangePointTestState(
            cusum_statistic=previous_state.cusum_statistic,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            processed_valid_count=previous_state.processed_valid_count,
            skipped_session_count=previous_state.skipped_session_count + 1,
            last_accepted_session_id=previous_state.last_accepted_session_id,
            last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
            provenance_identity=previous_state.provenance_identity or prov_identity,
            decision_status=ChangePointDecisionStatus.CHANGEPOINT_HORIZON_EXCEEDED,
            history_session_ids=previous_state.history_session_ids,
            calibration_context=previous_state.calibration_context,
        )
        update_res = ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=next_state,
            outcome=ChangePointProcessingOutcome.HORIZON_EXCEEDED,
            session_id=session_id,
            sequence_number=sequence_number,
            session_log_likelihood_ratio=0.0,
            applied_null_offset=null_offset_d,
            applied_threshold=emp_crit_val,
            active_run_length=previous_state.active_run_length,
            estimated_excursion_onset=previous_state.estimated_excursion_onset,
            diagnostic_reason=calib_dec.diagnostic_reason,
        )
        return update_res, calib_dec

    # Initialize calibration context on state if not present
    current_context = previous_state.calibration_context or StreamChangePointContext(
        calibration_p=calibration_p,
        horizon_sessions=horizon_sessions,
        artifact_content_hash=artifact.content_hash,
        calibration_guarantee="HORIZON_BOUNDED",
    )

    state_with_ctx = ChangePointTestState(
        cusum_statistic=previous_state.cusum_statistic,
        active_run_length=previous_state.active_run_length,
        estimated_excursion_onset=previous_state.estimated_excursion_onset,
        processed_valid_count=previous_state.processed_valid_count,
        skipped_session_count=previous_state.skipped_session_count,
        last_accepted_session_id=previous_state.last_accepted_session_id,
        last_accepted_sequence_number=previous_state.last_accepted_sequence_number,
        provenance_identity=previous_state.provenance_identity or prov_identity,
        decision_status=previous_state.decision_status,
        history_session_ids=previous_state.history_session_ids,
        calibration_context=current_context,
    )

    # Step 4: Execute underlying detector update with artifact offset & threshold
    update_res = update_changepoint_detector(
        state_with_ctx,
        evidence,
        stage1_result,
        sequence_number,
        prov_identity,
        null_offset_d=null_offset_d,
        threshold=emp_crit_val,
    )

    if update_res.outcome == ChangePointProcessingOutcome.EVIDENCE_ACCEPTED:
        is_elevated = update_res.next_state.cusum_statistic >= emp_crit_val
        dec_status = (
            ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED
            if is_elevated
            else ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_NOMINAL
        )

        final_next_state = ChangePointTestState(
            cusum_statistic=update_res.next_state.cusum_statistic,
            active_run_length=update_res.next_state.active_run_length,
            estimated_excursion_onset=update_res.next_state.estimated_excursion_onset,
            processed_valid_count=update_res.next_state.processed_valid_count,
            skipped_session_count=update_res.next_state.skipped_session_count,
            last_accepted_session_id=update_res.next_state.last_accepted_session_id,
            last_accepted_sequence_number=update_res.next_state.last_accepted_sequence_number,
            provenance_identity=update_res.next_state.provenance_identity,
            decision_status=dec_status,
            history_session_ids=update_res.next_state.history_session_ids,
            calibration_context=current_context,
        )

        final_update_res = ChangePointUpdateResult(
            previous_state=previous_state,
            next_state=final_next_state,
            outcome=update_res.outcome,
            session_id=update_res.session_id,
            sequence_number=update_res.sequence_number,
            session_log_likelihood_ratio=update_res.session_log_likelihood_ratio,
            applied_null_offset=null_offset_d,
            applied_threshold=emp_crit_val,
            active_run_length=final_next_state.active_run_length,
            estimated_excursion_onset=final_next_state.estimated_excursion_onset,
            diagnostic_reason=update_res.diagnostic_reason,
        )

        calib_dec = CalibratedChangePointDecision(
            session_id=session_id,
            sequence_number=sequence_number,
            cusum_statistic=final_next_state.cusum_statistic,
            active_run_length=final_next_state.active_run_length,
            estimated_excursion_onset=final_next_state.estimated_excursion_onset,
            processed_valid_count=final_next_state.processed_valid_count,
            calibration_p=calibration_p,
            matched_calibration_p=matched_p,
            null_offset_d=null_offset_d,
            empirical_critical_value=emp_crit_val,
            horizon_sessions=horizon_sessions,
            decision_status=dec_status,
            outcome=ChangePointProcessingOutcome.EVIDENCE_ACCEPTED,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            changepoint_model_version=artifact.changepoint_model_version,
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason=f"Accepted evidence log_lambda={final_update_res.session_log_likelihood_ratio:.6f}, offset d={null_offset_d:.6f}. CUSUM={final_next_state.cusum_statistic:.6f} vs threshold {emp_crit_val:.6f}.",
        )
        return final_update_res, calib_dec

    # For other outcomes
    calib_dec = CalibratedChangePointDecision(
        session_id=session_id,
        sequence_number=sequence_number,
        cusum_statistic=update_res.next_state.cusum_statistic,
        active_run_length=update_res.next_state.active_run_length,
        estimated_excursion_onset=update_res.next_state.estimated_excursion_onset,
        processed_valid_count=update_res.next_state.processed_valid_count,
        calibration_p=calibration_p,
        matched_calibration_p=matched_p,
        null_offset_d=null_offset_d,
        empirical_critical_value=emp_crit_val,
        horizon_sessions=horizon_sessions,
        decision_status=previous_state.decision_status,
        outcome=update_res.outcome,
        artifact_content_hash=artifact.content_hash,
        artifact_schema_version=artifact.schema_version,
        architecture_version=artifact.architecture_version,
        changepoint_model_version=artifact.changepoint_model_version,
        calibration_guarantee="HORIZON_BOUNDED",
        diagnostic_reason=update_res.diagnostic_reason,
    )
    return update_res, calib_dec
