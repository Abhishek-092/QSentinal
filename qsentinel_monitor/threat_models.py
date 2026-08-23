"""
Phase 9 Unified Threat Assessment & Monitoring Dataclasses for QSENTINEL.

Defines unified security posture enums, threat severities, unified state containers,
provenance bundles, and threat assessment contracts.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any

from qds.transcript import ProtocolDecision, SessionTranscript
from qsentinel_monitor.quantum_evidence.models import (
    QuantumEvidence,
    Stage1Result,
    CalibratedStage1Decision,
    CalibratedDecisionStatus,
)
from qsentinel_monitor.sequential_test_models import (
    SequentialTestState,
    CalibratedStage2Decision,
    Stage2DecisionStatus,
)
from qsentinel_monitor.changepoint_models import (
    ChangePointTestState,
    CalibratedChangePointDecision,
    ChangePointDecisionStatus,
)


class SecurityPosture(str, Enum):
    NOMINAL = "NOMINAL"
    ELEVATED_STAGE1 = "ELEVATED_STAGE1"
    ELEVATED_STAGE2 = "ELEVATED_STAGE2"
    ELEVATED_CHANGEPOINT = "ELEVATED_CHANGEPOINT"
    ELEVATED_CRITICAL = "ELEVATED_CRITICAL"  # Multiple detectors elevated
    EXPIRED_HORIZON = "EXPIRED_HORIZON"
    UNAVAILABLE = "UNAVAILABLE"


class ThreatSeverity(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ProvenanceBundle:
    stage1_artifact_hash: Optional[str]
    stage2_artifact_hash: Optional[str]
    changepoint_artifact_hash: Optional[str]
    architecture_version: str = "v9.0"


@dataclass(frozen=True)
class UnifiedThreatAssessment:
    session_id: str
    sequence_number: int
    security_posture: SecurityPosture
    threat_severity: ThreatSeverity
    contributing_detectors: Tuple[str, ...]
    explanation: str
    estimated_excursion_onset: Optional[int]
    stage2_horizon_exceeded: bool
    changepoint_horizon_exceeded: bool
    provenance_bundle: ProvenanceBundle


@dataclass(frozen=True)
class UnifiedMonitoringState:
    sequence_number: int
    stage2_state: SequentialTestState
    changepoint_state: ChangePointTestState


@dataclass(frozen=True)
class UnifiedMonitoringResult:
    session_id: str
    sequence_number: int
    protocol_decision: ProtocolDecision  # Unmutated frozen object
    evidence: QuantumEvidence
    stage1_result: Stage1Result
    calibrated_stage1_decision: Optional[CalibratedStage1Decision]
    calibrated_stage2_decision: Optional[CalibratedStage2Decision]
    calibrated_changepoint_decision: Optional[CalibratedChangePointDecision]
    threat_assessment: UnifiedThreatAssessment
    next_unified_state: UnifiedMonitoringState
    is_advisory: bool = True
