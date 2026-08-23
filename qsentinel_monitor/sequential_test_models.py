"""
Stage 2 Joint Sequential Likelihood Test Domain Models & State Contracts for QSENTINEL (Phase 6D).

Extends Stage 2 domain models with calibrated decision statuses, outcomes,
stream calibration operating context, and Stage 2 calibrated decisions.
All domain objects are deeply immutable dataclasses using frozen tuples.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from qsentinel_monitor.quantum_evidence.models import Stage1Result, QuantumEvidence


class Stage2DecisionStatus(str, Enum):
    STAGE2_NOMINAL = "STAGE2_NOMINAL"
    STAGE2_EVIDENCE_ELEVATED = "STAGE2_EVIDENCE_ELEVATED"
    STAGE2_UNINITIALIZED = "STAGE2_UNINITIALIZED"
    STAGE2_PROVENANCE_MISMATCH = "STAGE2_PROVENANCE_MISMATCH"
    STAGE2_UNAVAILABLE = "STAGE2_UNAVAILABLE"
    STAGE2_CALIBRATED_NOMINAL = "STAGE2_CALIBRATED_NOMINAL"
    STAGE2_CALIBRATED_ELEVATED = "STAGE2_CALIBRATED_ELEVATED"
    STAGE2_HORIZON_EXCEEDED = "STAGE2_HORIZON_EXCEEDED"
    STAGE2_CALIBRATION_UNAVAILABLE = "STAGE2_CALIBRATION_UNAVAILABLE"
    STAGE2_OUT_OF_SUPPORT = "STAGE2_OUT_OF_SUPPORT"


class Stage2ProcessingOutcome(str, Enum):
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    DUPLICATE_SESSION = "DUPLICATE_SESSION"
    OUT_OF_ORDER_SESSION = "OUT_OF_ORDER_SESSION"
    INCOMPATIBLE_PROVENANCE = "INCOMPATIBLE_PROVENANCE"
    UNAVAILABLE_INPUT = "UNAVAILABLE_INPUT"
    INVALID_NUMERICAL_INPUT = "INVALID_NUMERICAL_INPUT"
    HORIZON_EXCEEDED = "HORIZON_EXCEEDED"
    CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"
    OUT_OF_SUPPORT = "OUT_OF_SUPPORT"


@dataclass(frozen=True)
class Stage2ProvenanceIdentity:
    """
    Immutable provenance identity for Stage 2 sequential likelihood testing.
    Tied to Stage 2 calibration artifact content hash and model versions.
    """
    artifact_content_hash: str
    artifact_schema_version: str
    architecture_version: str
    stage1_model_version: str
    stage2_model_version: str = "v1.0"


@dataclass(frozen=True)
class StreamCalibrationContext:
    """
    Immutable operating-point calibration context frozen at stream initialization.
    Fixes operating noise parameter p and horizon H for the stream.
    """
    calibration_p: float
    horizon_sessions: int
    artifact_content_hash: str
    calibration_guarantee: str = "HORIZON_BOUNDED"


@dataclass(frozen=True)
class SequentialTestState:
    """
    Immutable state tracking cumulative sequential generalized likelihood ratio (GLR) evidence across sessions.
    """
    cumulative_log_likelihood_ratio: float
    processed_valid_count: int
    skipped_session_count: int
    last_accepted_session_id: Optional[str]
    last_accepted_sequence_number: int
    provenance_identity: Optional[Stage2ProvenanceIdentity]
    decision_status: Stage2DecisionStatus
    history_session_ids: Tuple[str, ...]
    calibration_context: Optional[StreamCalibrationContext] = None


@dataclass(frozen=True)
class SequentialTestUpdateResult:
    """
    Immutable result of updating Stage 2 sequential test state with a new session.
    """
    previous_state: SequentialTestState
    next_state: SequentialTestState
    outcome: Stage2ProcessingOutcome
    session_id: str
    sequence_number: int
    session_log_likelihood_ratio: float
    applied_threshold: Optional[float]
    diagnostic_reason: str


@dataclass(frozen=True)
class CalibratedStage2Decision:
    """
    Immutable result of applying a loaded Stage 2 calibration artifact to a Stage 2 update.
    Preserves end-to-end auditability and horizon-bounded false alarm guarantees.
    """
    session_id: str
    sequence_number: int
    cumulative_log_likelihood_ratio: float
    processed_valid_count: int
    calibration_p: float
    matched_calibration_p: Optional[float]
    empirical_critical_value: Optional[float]
    horizon_sessions: int
    decision_status: Stage2DecisionStatus
    outcome: Stage2ProcessingOutcome
    artifact_content_hash: str
    artifact_schema_version: str
    architecture_version: str
    stage2_model_version: str
    calibration_guarantee: str
    diagnostic_reason: str
