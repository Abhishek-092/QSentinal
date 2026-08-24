"""
Phase 9 Unified Monitoring Orchestrator & Threat Assessment Engine for QSENTINEL.

Composes Stage 1, Stage 2, and Change-Point detectors into an authoritative, deterministic
threat assessment pipeline.

PERFORMS ZERO MONTE CARLO, ZERO SEED ALLOCATION, ZERO SIMULATION, ZERO PROTOCOL MUTATION,
AND ZERO RUNTIME CALIBRATION.
"""


from qds.transcript import SessionTranscript
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1
from qsentinel_monitor.calibration_loader import CalibrationArtifact
from qsentinel_monitor.calibrated_decision import evaluate_calibrated_stage1
from qsentinel_monitor.quantum_evidence.models import (
    QuantumEvidence,
    Stage1Result,
    CalibratedStage1Decision,
    CalibratedDecisionStatus,
)
from qsentinel_monitor.stage2_calibration_loader import Stage2CalibrationArtifact
from qsentinel_monitor.stage2_calibrated_decision import evaluate_calibrated_stage2
from qsentinel_monitor.sequential_test import create_initial_stage2_state
from qsentinel_monitor.sequential_test_models import (
    SequentialTestState,
    CalibratedStage2Decision,
    Stage2DecisionStatus,
)
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact
from qsentinel_monitor.changepoint_calibrated_decision import evaluate_calibrated_changepoint
from qsentinel_monitor.changepoint_detector import create_initial_changepoint_state
from qsentinel_monitor.changepoint_models import (
    ChangePointTestState,
    CalibratedChangePointDecision,
    ChangePointDecisionStatus,
)
from qsentinel_monitor.threat_models import (
    SecurityPosture,
    ThreatSeverity,
    ProvenanceBundle,
    UnifiedThreatAssessment,
    UnifiedMonitoringState,
    UnifiedMonitoringResult,
)


def create_initial_unified_state() -> UnifiedMonitoringState:
    """Creates initial empty UnifiedMonitoringState (sequence_number=0)."""
    return UnifiedMonitoringState(
        sequence_number=0,
        stage2_state=create_initial_stage2_state(),
        changepoint_state=create_initial_changepoint_state(),
    )


def evaluate_unified_threat(
    session_id: str,
    sequence_number: int,
    stage1_dec: CalibratedStage1Decision | None,
    stage2_dec: CalibratedStage2Decision | None,
    changepoint_dec: CalibratedChangePointDecision | None,
    stage1_artifact: CalibrationArtifact | None = None,
    stage2_artifact: Stage2CalibrationArtifact | None = None,
    changepoint_artifact: ChangePointCalibrationArtifact | None = None,
) -> UnifiedThreatAssessment:
    """
    Synthesizes individual detector decisions into an authoritative UnifiedThreatAssessment.
    Enforces deterministic severity escalation, contributing detector aggregation, and provenance bundling.
    """
    contributing: list[str] = []
    st1_elevated = (
        stage1_dec is not None
        and stage1_dec.decision == CalibratedDecisionStatus.MODEL_INCONSISTENT
    )
    st2_elevated = (
        stage2_dec is not None
        and stage2_dec.decision_status == Stage2DecisionStatus.STAGE2_CALIBRATED_ELEVATED
    )
    cp_elevated = (
        changepoint_dec is not None
        and changepoint_dec.decision_status == ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED
    )

    if st1_elevated:
        contributing.append("STAGE_1_PROFILE_LIKELIHOOD")
    if st2_elevated:
        contributing.append("STAGE_2_CUMULATIVE_GLR")
    if cp_elevated:
        contributing.append("OFFSET_GLR_CUSUM_CHANGEPOINT")

    # Horizon exceedance flags
    st2_hz_exceeded = (
        stage2_dec is not None
        and stage2_dec.decision_status == Stage2DecisionStatus.STAGE2_HORIZON_EXCEEDED
    )
    cp_hz_exceeded = (
        changepoint_dec is not None
        and changepoint_dec.decision_status == ChangePointDecisionStatus.CHANGEPOINT_HORIZON_EXCEEDED
    )

    # Excursion onset
    onset_est = changepoint_dec.estimated_excursion_onset if changepoint_dec else None

    # Determine security posture and threat severity
    num_elevated = len(contributing)

    if num_elevated >= 2:
        posture = SecurityPosture.ELEVATED_CRITICAL
        severity = ThreatSeverity.CRITICAL
        explanation = f"Critical multi-detector threat detected ({', '.join(contributing)} elevated)."
    elif st2_elevated:
        posture = SecurityPosture.ELEVATED_STAGE2
        severity = ThreatSeverity.HIGH
        explanation = "Stage 2 cumulative GLR evidence crossed calibrated threshold."
    elif cp_elevated:
        posture = SecurityPosture.ELEVATED_CHANGEPOINT
        severity = ThreatSeverity.HIGH
        explanation = f"Offset GLR-CUSUM change-point detector elevated (estimated excursion onset session {onset_est})."
    elif st1_elevated:
        posture = SecurityPosture.ELEVATED_STAGE1
        severity = ThreatSeverity.MEDIUM
        explanation = "Stage 1 profile-likelihood mutual consistency test failed."
    elif st2_hz_exceeded or cp_hz_exceeded:
        posture = SecurityPosture.EXPIRED_HORIZON
        severity = ThreatSeverity.INFORMATIONAL
        explanation = "Monitoring horizon limit reached for one or more sequential detectors."
    else:
        posture = SecurityPosture.NOMINAL
        severity = ThreatSeverity.INFORMATIONAL
        explanation = "All active monitoring detectors report nominal execution."

    prov_bundle = ProvenanceBundle(
        stage1_artifact_hash=stage1_artifact.content_hash if stage1_artifact else (stage1_dec.artifact_content_hash if stage1_dec else None),
        stage2_artifact_hash=stage2_artifact.content_hash if stage2_artifact else (stage2_dec.artifact_content_hash if stage2_dec else None),
        changepoint_artifact_hash=changepoint_artifact.content_hash if changepoint_artifact else (changepoint_dec.artifact_content_hash if changepoint_dec else None),
        architecture_version="v9.0",
    )

    return UnifiedThreatAssessment(
        session_id=session_id,
        sequence_number=sequence_number,
        security_posture=posture,
        threat_severity=severity,
        contributing_detectors=tuple(contributing),
        explanation=explanation,
        estimated_excursion_onset=onset_est,
        stage2_horizon_exceeded=st2_hz_exceeded,
        changepoint_horizon_exceeded=cp_hz_exceeded,
        provenance_bundle=prov_bundle,
    )


def analyze_unified_session(
    transcript: SessionTranscript,
    previous_unified_state: UnifiedMonitoringState | None = None,
    stage1_artifact: CalibrationArtifact | None = None,
    stage2_artifact: Stage2CalibrationArtifact | None = None,
    changepoint_artifact: ChangePointCalibrationArtifact | None = None,
    calibration_p: float = 0.02,
) -> UnifiedMonitoringResult:
    """
    Orchestrates unified multi-detector monitoring on a SessionTranscript.
    
    Pipeline Steps:
    1. Extract QuantumEvidence from SessionTranscript.
    2. Evaluate Stage 1 profile-likelihood test (and optional calibrated decision).
    3. Evaluate Stage 2 cumulative GLR test (if artifact provided).
    4. Evaluate Offset GLR-CUSUM change-point test (if artifact provided).
    5. Synthesize UnifiedThreatAssessment.
    6. Return UnifiedMonitoringResult with next_unified_state.
    """
    session_id = transcript.session_id

    if previous_unified_state is None:
        state = create_initial_unified_state()
    else:
        state = previous_unified_state

    seq_num = state.sequence_number + 1

    evidence: QuantumEvidence = extract_evidence(transcript)

    stage1_res: Stage1Result = evaluate_stage1(evidence)
    st1_dec: CalibratedStage1Decision | None = None
    if stage1_artifact is not None:
        st1_dec = evaluate_calibrated_stage1(stage1_res, stage1_artifact)

    st2_dec: CalibratedStage2Decision | None = None
    next_st2_state = state.stage2_state
    if stage2_artifact is not None:
        up_st2, st2_dec = evaluate_calibrated_stage2(
            previous_state=state.stage2_state,
            evidence=evidence,
            stage1_result=stage1_res,
            sequence_number=seq_num,
            calibration_p=calibration_p,
            artifact=stage2_artifact,
        )
        next_st2_state = up_st2.next_state

    cp_dec: CalibratedChangePointDecision | None = None
    next_cp_state = state.changepoint_state
    if changepoint_artifact is not None:
        up_cp, cp_dec = evaluate_calibrated_changepoint(
            previous_state=state.changepoint_state,
            evidence=evidence,
            stage1_result=stage1_res,
            sequence_number=seq_num,
            calibration_p=calibration_p,
            artifact=changepoint_artifact,
        )
        next_cp_state = up_cp.next_state

    threat_assessment = evaluate_unified_threat(
        session_id=session_id,
        sequence_number=seq_num,
        stage1_dec=st1_dec,
        stage2_dec=st2_dec,
        changepoint_dec=cp_dec,
        stage1_artifact=stage1_artifact,
        stage2_artifact=stage2_artifact,
        changepoint_artifact=changepoint_artifact,
    )

    next_unified_state = UnifiedMonitoringState(
        sequence_number=seq_num,
        stage2_state=next_st2_state,
        changepoint_state=next_cp_state,
    )

    return UnifiedMonitoringResult(
        session_id=session_id,
        sequence_number=seq_num,
        protocol_decision=transcript.protocol_decision,  # Unmutated frozen object
        evidence=evidence,
        stage1_result=stage1_res,
        calibrated_stage1_decision=st1_dec,
        calibrated_stage2_decision=st2_dec,
        calibrated_changepoint_decision=cp_dec,
        threat_assessment=threat_assessment,
        next_unified_state=next_unified_state,
        is_advisory=True,
    )
