"""
QSENTINEL Threat Orchestrator.
Connects immutable SessionTranscript & ProtocolDecision -> Evidence Collection -> Stage 1.
Guarantees absolute non-interference: Monitoring output is strictly advisory and NEVER mutates ProtocolDecision.
"""
from qds.transcript import SessionTranscript, ProtocolDecision
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1
from qsentinel_monitor.quantum_evidence.models import MonitoringResult, QuantumEvidence, Stage1Result


def analyze_session(transcript: SessionTranscript) -> MonitoringResult:
    """
    Orchestrates post-session advisory monitoring on a finalized SessionTranscript.

    NON-INTERFERENCE GUARANTEES:
    - Does NOT mutate transcript or transcript.protocol_decision.
    - Returns separate MonitoringResult containing protocol_decision, evidence, and stage1_result.
    - Never alters ProtocolDecision.accepted or ProtocolDecision.reason.
    """
    # 1. Extract quantum evidence telemetry
    evidence: QuantumEvidence = extract_evidence(transcript)

    # 2. Evaluate Stage 1 profile-likelihood mutual consistency
    stage1_res: Stage1Result = evaluate_stage1(evidence)

    # 3. Advisory monitoring status (Non-final / advisory)
    monitoring_status = "MONITORED_ADVISORY"

    return MonitoringResult(
        session_id=transcript.session_id,
        protocol_decision=transcript.protocol_decision,  # Unmutated frozen object
        monitoring_status=monitoring_status,
        evidence=evidence,
        stage1_result=stage1_res,
        is_advisory=True,
    )
