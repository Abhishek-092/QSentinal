"""
Phase 11 Session Submission API Router for QSENTINEL.
"""
from fastapi import APIRouter, Depends, HTTPException
from qds.transcript import SessionTranscript, ProtocolDecision
from qsentinel_api.schemas import (
    SessionSubmissionRequest,
    UnifiedMonitoringResultSchema,
    ProtocolDecisionSchema,
    QuantumEvidenceSchema,
    Stage1ResultSchema,
    UnifiedThreatAssessmentSchema,
    ProvenanceBundleSchema,
)
from qsentinel_api.dependencies import get_db_path
from qsentinel_monitor.lifecycle.session_runner import TransactionalSessionRunner
from qsentinel_monitor.persistence.repositories import EpochRepository, ArtifactRepository
from qsentinel_monitor.calibration_loader import CalibrationArtifact
from qsentinel_monitor.stage2_calibration_loader import Stage2CalibrationArtifact
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact

router = APIRouter(prefix="/streams/{stream_id}/epochs/{epoch_id}/sessions", tags=["Session Submission"])


def _convert_schema_to_domain_transcript(s: SessionSubmissionRequest) -> SessionTranscript:
    ts = s.transcript
    pd = ProtocolDecision(
        accepted=ts.protocol_decision.accepted,
        reason=ts.protocol_decision.reason,
        mismatch_count=ts.protocol_decision.mismatch_count,
        sifted_length=ts.protocol_decision.sifted_length,
        s_a=ts.protocol_decision.s_a,
        s_v=ts.protocol_decision.s_v,
        session_id=ts.protocol_decision.session_id,
    )
    return SessionTranscript(
        session_id=ts.session_id,
        timestamp=ts.timestamp,
        sender_id=ts.sender_id,
        recipient_id=ts.recipient_id,
        auth_token=ts.auth_token,
        nonce=ts.nonce,
        message_bit=ts.message_bit,
        keys=tuple(ts.keys),
        bases=tuple(ts.bases),
        recipient_bases=tuple(ts.recipient_bases),
        bell_outcomes=tuple(tuple(x) for x in ts.bell_outcomes),
        raw_measurements=tuple(ts.raw_measurements),
        sifted_indices=tuple(ts.sifted_indices),
        mismatch_flags=tuple(ts.mismatch_flags),
        pauli_corrections_applied=tuple(tuple(x) for x in ts.pauli_corrections_applied),
        protocol_decision=pd,
        metadata=ts.metadata or {},
    )


@router.post("", response_model=UnifiedMonitoringResultSchema, status_code=200)
def submit_session(
    stream_id: str,
    epoch_id: str,
    req: SessionSubmissionRequest,
    db_path: str = Depends(get_db_path),
):
    """
    Submits a SessionTranscript for durable, transactional monitoring evaluation.
    Delegates exclusively to the authoritative TransactionalSessionRunner.
    """
    epoch = EpochRepository.get_epoch(db_path, epoch_id)
    if epoch is None or epoch.stream_id != stream_id:
        raise HTTPException(status_code=404, detail=f"Epoch {epoch_id} for stream {stream_id} not found.")

    # Load bound artifacts if present in DB
    st1_art = (
        CalibrationArtifact(**ArtifactRepository.get_artifact(db_path, epoch.stage1_artifact_hash))
        if epoch.stage1_artifact_hash
        else None
    )
    st2_art = (
        Stage2CalibrationArtifact(**ArtifactRepository.get_artifact(db_path, epoch.stage2_artifact_hash))
        if epoch.stage2_artifact_hash
        else None
    )
    cp_art = (
        ChangePointCalibrationArtifact(**ArtifactRepository.get_artifact(db_path, epoch.changepoint_artifact_hash))
        if epoch.changepoint_artifact_hash
        else None
    )

    domain_transcript = _convert_schema_to_domain_transcript(req)
    runner = TransactionalSessionRunner(db_path)

    # Delegate session processing exclusively to runner (handles idempotency, conflicts, transactions)
    res = runner.process_session(
        epoch_id=epoch_id,
        transcript=domain_transcript,
        stage1_artifact=st1_art,
        stage2_artifact=st2_art,
        changepoint_artifact=cp_art,
    )

    ta = res.threat_assessment
    return UnifiedMonitoringResultSchema(
        session_id=res.session_id,
        sequence_number=res.sequence_number,
        protocol_decision=ProtocolDecisionSchema(
            accepted=res.protocol_decision.accepted,
            reason=res.protocol_decision.reason,
            mismatch_count=res.protocol_decision.mismatch_count,
            sifted_length=res.protocol_decision.sifted_length,
            s_a=res.protocol_decision.s_a,
            s_v=res.protocol_decision.s_v,
            session_id=res.protocol_decision.session_id,
        ),
        evidence=QuantumEvidenceSchema(
            session_id=res.evidence.session_id,
            sample_count=res.evidence.sample_count,
            total_sifted_count=res.evidence.total_sifted_count,
            total_mismatch_count=res.evidence.total_mismatch_count,
            overall_mismatch_rate=res.evidence.overall_mismatch_rate,
            z_sifted_count=res.evidence.z_sifted_count,
            z_mismatch_count=res.evidence.z_mismatch_count,
            z_mismatch_rate=res.evidence.z_mismatch_rate,
            x_sifted_count=res.evidence.x_sifted_count,
            x_mismatch_count=res.evidence.x_mismatch_count,
            x_mismatch_rate=res.evidence.x_mismatch_rate,
        ),
        stage1_result=Stage1ResultSchema(
            session_id=res.stage1_result.session_id,
            status=res.stage1_result.status,
            best_fit_p=res.stage1_result.best_fit_p,
            statistic=res.stage1_result.statistic,
            uncalibrated_theoretical_p_value=res.stage1_result.uncalibrated_theoretical_p_value,
            optimization_success=res.stage1_result.optimization_success,
        ),
        threat_assessment=UnifiedThreatAssessmentSchema(
            session_id=ta.session_id,
            sequence_number=ta.sequence_number,
            security_posture=ta.security_posture.value,
            threat_severity=ta.threat_severity.value,
            contributing_detectors=list(ta.contributing_detectors),
            explanation=ta.explanation,
            estimated_excursion_onset=ta.estimated_excursion_onset,
            stage2_horizon_exceeded=ta.stage2_horizon_exceeded,
            changepoint_horizon_exceeded=ta.changepoint_horizon_exceeded,
            provenance_bundle=ProvenanceBundleSchema(
                stage1_artifact_hash=ta.provenance_bundle.stage1_artifact_hash,
                stage2_artifact_hash=ta.provenance_bundle.stage2_artifact_hash,
                changepoint_artifact_hash=ta.provenance_bundle.changepoint_artifact_hash,
                architecture_version=ta.provenance_bundle.architecture_version,
            ),
        ),
        is_advisory=res.is_advisory,
    )
