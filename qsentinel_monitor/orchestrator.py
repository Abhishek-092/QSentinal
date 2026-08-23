"""
QSENTINEL Threat Orchestrator.
Connects immutable SessionTranscript & ProtocolDecision -> Evidence Collection -> Stage 1 -> Optional Calibrated Decision.
Guarantees absolute non-interference: Monitoring output is strictly advisory and NEVER mutates ProtocolDecision.
"""
from typing import Optional
from qds.transcript import SessionTranscript, ProtocolDecision
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1
from qsentinel_monitor.quantum_evidence.models import (
    MonitoringResult,
    QuantumEvidence,
    Stage1Result,
    CalibratedStage1Decision,
)
from qsentinel_monitor.calibration_loader import CalibrationArtifact
from qsentinel_monitor.calibrated_decision import evaluate_calibrated_stage1


def analyze_session(
    transcript: SessionTranscript,
    calibration_artifact: Optional[CalibrationArtifact] = None,
) -> MonitoringResult:
    """
    Orchestrates post-session advisory monitoring on a finalized SessionTranscript.

    NON-INTERFERENCE GUARANTEES:
    - Does NOT mutate transcript or transcript.protocol_decision.
    - Returns separate MonitoringResult containing protocol_decision, evidence, stage1_result,
      and optional calibrated_decision.
    - Never alters ProtocolDecision.accepted or ProtocolDecision.reason.
    """
    # 1. Extract quantum evidence telemetry
    evidence: QuantumEvidence = extract_evidence(transcript)

    # 2. Evaluate Stage 1 profile-likelihood mutual consistency
    stage1_res: Stage1Result = evaluate_stage1(evidence)

    # 3. Optional calibrated decision evaluation via dependency injection
    calibrated_dec: Optional[CalibratedStage1Decision] = None
    if calibration_artifact is not None:
        calibrated_dec = evaluate_calibrated_stage1(stage1_res, calibration_artifact)

    # 4. Advisory monitoring status (Non-final / advisory)
    monitoring_status = "MONITORED_ADVISORY"

    return MonitoringResult(
        session_id=transcript.session_id,
        protocol_decision=transcript.protocol_decision,  # Unmutated frozen object
        monitoring_status=monitoring_status,
        evidence=evidence,
        stage1_result=stage1_res,
        calibrated_decision=calibrated_dec,
        is_advisory=True,
    )
