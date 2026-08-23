"""
Phase 11 Epoch Management API Router for QSENTINEL.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from qsentinel_api.schemas import (
    EpochCreateRequest,
    EpochRenewRequest,
    EpochResponse,
    MonitoringStateResponseSchema,
    UnifiedThreatAssessmentSchema,
    ProvenanceBundleSchema,
)
from qsentinel_api.dependencies import get_db_path
from qsentinel_monitor.lifecycle.stream_manager import StreamLifecycleManager
from qsentinel_monitor.persistence.repositories import (
    EpochRepository,
    StreamRepository,
    SessionRepository,
)

router = APIRouter(prefix="/streams/{stream_id}/epochs", tags=["Epoch Management"])


@router.post("", response_model=EpochResponse, status_code=201)
def create_epoch(stream_id: str, req: EpochCreateRequest, db_path: str = Depends(get_db_path)):
    """Creates a new monitoring epoch bound to explicit artifacts and calibration context."""
    if StreamRepository.get_stream(db_path, stream_id) is None:
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found.")

    mgr = StreamLifecycleManager(db_path)
    context = {"calibration_p": req.calibration_p}
    if req.additional_context:
        context.update(req.additional_context)

    epoch_rec = mgr.create_epoch(stream_id=stream_id, calibration_context=context)
    return EpochResponse(
        epoch_id=epoch_rec.epoch_id,
        stream_id=epoch_rec.stream_id,
        epoch_index=epoch_rec.epoch_index,
        status=epoch_rec.status,
        termination_reason=epoch_rec.termination_reason,
        stage1_artifact_hash=epoch_rec.stage1_artifact_hash,
        stage2_artifact_hash=epoch_rec.stage2_artifact_hash,
        changepoint_artifact_hash=epoch_rec.changepoint_artifact_hash,
        calibration_context=json.loads(epoch_rec.calibration_context_json),
        created_at=epoch_rec.created_at,
        closed_at=epoch_rec.closed_at,
    )


@router.get("/{epoch_id}", response_model=EpochResponse)
def get_epoch(stream_id: str, epoch_id: str, db_path: str = Depends(get_db_path)):
    """Retrieves epoch lifecycle status and calibration context."""
    rec = EpochRepository.get_epoch(db_path, epoch_id)
    if rec is None or rec.stream_id != stream_id:
        raise HTTPException(status_code=404, detail=f"Epoch {epoch_id} for stream {stream_id} not found.")
    return EpochResponse(
        epoch_id=rec.epoch_id,
        stream_id=rec.stream_id,
        epoch_index=rec.epoch_index,
        status=rec.status,
        termination_reason=rec.termination_reason,
        stage1_artifact_hash=rec.stage1_artifact_hash,
        stage2_artifact_hash=rec.stage2_artifact_hash,
        changepoint_artifact_hash=rec.changepoint_artifact_hash,
        calibration_context=json.loads(rec.calibration_context_json),
        created_at=rec.created_at,
        closed_at=rec.closed_at,
    )


@router.post("/{epoch_id}/renew", response_model=EpochResponse)
def renew_epoch(stream_id: str, epoch_id: str, req: EpochRenewRequest, db_path: str = Depends(get_db_path)):
    """Closes current epoch and spawns clean epoch_index + 1 bound to new calibration context."""
    rec = EpochRepository.get_epoch(db_path, epoch_id)
    if rec is None or rec.stream_id != stream_id:
        raise HTTPException(status_code=404, detail=f"Epoch {epoch_id} for stream {stream_id} not found.")

    mgr = StreamLifecycleManager(db_path)
    context = {"calibration_p": req.calibration_p}
    if req.additional_context:
        context.update(req.additional_context)

    new_epoch = mgr.renew_epoch(
        stream_id=stream_id,
        calibration_context=context,
        termination_reason=req.termination_reason or "EXPLICIT_RENEWAL",
    )
    return EpochResponse(
        epoch_id=new_epoch.epoch_id,
        stream_id=new_epoch.stream_id,
        epoch_index=new_epoch.epoch_index,
        status=new_epoch.status,
        termination_reason=new_epoch.termination_reason,
        stage1_artifact_hash=new_epoch.stage1_artifact_hash,
        stage2_artifact_hash=new_epoch.stage2_artifact_hash,
        changepoint_artifact_hash=new_epoch.changepoint_artifact_hash,
        calibration_context=json.loads(new_epoch.calibration_context_json),
        created_at=new_epoch.created_at,
        closed_at=new_epoch.closed_at,
    )


@router.get("/{epoch_id}/state", response_model=MonitoringStateResponseSchema)
def get_epoch_monitoring_state(stream_id: str, epoch_id: str, db_path: str = Depends(get_db_path)):
    """Retrieves current restored detector state snapshot for an epoch."""
    epoch = EpochRepository.get_epoch(db_path, epoch_id)
    if epoch is None or epoch.stream_id != stream_id:
        raise HTTPException(status_code=404, detail=f"Epoch {epoch_id} for stream {stream_id} not found.")

    snap_tuple = SessionRepository.get_latest_snapshot(db_path, epoch_id)
    if snap_tuple is None:
        return MonitoringStateResponseSchema(
            epoch_id=epoch_id,
            sequence_number=0,
            epoch_status=epoch.status,
            stage2_processed_count=0,
            stage2_decision_status="CHANGEPOINT_UNINITIALIZED",
            stage2_cumulative_glr=0.0,
            changepoint_processed_count=0,
            changepoint_decision_status="CHANGEPOINT_UNINITIALIZED",
            changepoint_cusum_statistic=0.0,
            changepoint_active_run_length=0,
            changepoint_estimated_onset=None,
        )

    st, _ = snap_tuple
    return MonitoringStateResponseSchema(
        epoch_id=epoch_id,
        sequence_number=st.sequence_number,
        epoch_status=epoch.status,
        stage2_processed_count=st.stage2_state.processed_valid_count,
        stage2_decision_status=st.stage2_state.decision_status.value,
        stage2_cumulative_glr=st.stage2_state.cumulative_log_likelihood_ratio,
        changepoint_processed_count=st.changepoint_state.processed_valid_count,
        changepoint_decision_status=st.changepoint_state.decision_status.value,
        changepoint_cusum_statistic=st.changepoint_state.cusum_statistic,
        changepoint_active_run_length=st.changepoint_state.active_run_length,
        changepoint_estimated_onset=st.changepoint_state.estimated_excursion_onset,
    )


@router.get("/{epoch_id}/assessment", response_model=UnifiedThreatAssessmentSchema)
def get_latest_threat_assessment(stream_id: str, epoch_id: str, db_path: str = Depends(get_db_path)):
    """Retrieves the latest persisted authoritative threat assessment for an epoch."""
    epoch = EpochRepository.get_epoch(db_path, epoch_id)
    if epoch is None or epoch.stream_id != stream_id:
        raise HTTPException(status_code=404, detail=f"Epoch {epoch_id} for stream {stream_id} not found.")

    snap_tuple = SessionRepository.get_latest_snapshot(db_path, epoch_id)
    if snap_tuple is None:
        raise HTTPException(status_code=404, detail=f"No sessions processed yet in epoch {epoch_id}.")

    latest_seq = snap_tuple[0].sequence_number
    # Query threat assessment by session ID associated with latest sequence
    from qsentinel_monitor.persistence.database import get_connection
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT session_id FROM monitoring_sessions WHERE epoch_id = ? AND sequence_number = ?",
        (epoch_id, latest_seq),
    ).fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"No session found for sequence {latest_seq}.")

    ta = SessionRepository.get_threat_assessment(db_path, epoch_id, row["session_id"])
    if ta is None:
        raise HTTPException(status_code=404, detail="Threat assessment not found.")

    return UnifiedThreatAssessmentSchema(
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
    )
