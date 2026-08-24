"""
QSENTINEL Threat Orchestrator.
Connects immutable SessionTranscript & ProtocolDecision -> Evidence Collection -> Stage 1 -> Optional Calibrated Decision.
Guarantees absolute non-interference: Monitoring output is strictly advisory and NEVER mutates ProtocolDecision.
"""

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
from qsentinel_monitor.stage2_calibration_loader import Stage2CalibrationArtifact
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact
from qsentinel_monitor.threat_models import UnifiedMonitoringState
from qsentinel_monitor.calibrated_decision import evaluate_calibrated_stage1


from dataclasses import dataclass

@dataclass(frozen=True)
class MonitoringDecision:
    session_id: str
    verdict: str
    advisory: bool
    stage1_passed: bool
    details: str
    stage2_passed: bool = True
    fsm_passed: bool = True
    cusum_value: float = 0.0
    drift_detected: bool = False



def analyze_session(
    transcript: SessionTranscript,
    calibration_artifact: CalibrationArtifact | None = None,
    stage2_artifact: Stage2CalibrationArtifact | None = None,
    changepoint_artifact: ChangePointCalibrationArtifact | None = None,
    previous_unified_state: UnifiedMonitoringState | None = None,
    calibration_p: float = 0.02,
) -> MonitoringResult:
    """
    Orchestrates post-session advisory monitoring on a finalized SessionTranscript.

    NON-INTERFERENCE GUARANTEES:
    - Does NOT mutate transcript or transcript.protocol_decision.
    - Returns separate MonitoringResult containing protocol_decision, evidence, stage1_result,
      and optional calibrated_decision.
    - Never alters ProtocolDecision.accepted or ProtocolDecision.reason.
    """
    evidence: QuantumEvidence = extract_evidence(transcript)

    stage1_res: Stage1Result = evaluate_stage1(evidence)

    calibrated_dec: CalibratedStage1Decision | None = None
    if calibration_artifact is not None:
        calibrated_dec = evaluate_calibrated_stage1(stage1_res, calibration_artifact)

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


def analyze(transcript: SessionTranscript, protocol_decision: ProtocolDecision) -> MonitoringDecision:
    """Legacy/convenience wrapper for advisory monitoring analysis."""
    res = analyze_session(transcript)
    mismatch_rate = res.evidence.overall_mismatch_rate
    if not res.stage1_result.passed:
        verdict = "MODEL_INVALID" if res.stage1_result.optimizer_converged is False else "FLAG_REJECT"
    elif mismatch_rate > 0.10:
        verdict = "FLAG_REJECT"
    elif mismatch_rate > 0.05:
        verdict = "FLAG_INVESTIGATE"
    else:
        verdict = "ACCEPT"
    
    stage2_passed = verdict in ("ACCEPT", "FLAG_INVESTIGATE")
    return MonitoringDecision(
        session_id=transcript.session_id,
        verdict=verdict,
        advisory=True,
        stage1_passed=res.stage1_result.passed,
        stage2_passed=stage2_passed,
        fsm_passed=True,
        cusum_value=0.0,
        drift_detected=False,
        details=res.stage1_result.details,
    )



@dataclass(frozen=True)
class CalibrationInfo:
    content_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"
    rejection_threshold: float = 3.841
    s_sprt_threshold: float = 2.0
    s_gate_threshold: float = 0.8
    metadata: dict | None = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


_calibration: CalibrationInfo | None = None


def get_calibration() -> CalibrationInfo:
    global _calibration
    if _calibration is None:
        _calibration = CalibrationInfo()
    return _calibration



