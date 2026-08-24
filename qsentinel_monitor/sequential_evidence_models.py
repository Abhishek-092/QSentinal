"""
Phase 6B/6C Sequential Evidence Domain Models & State Transitions for QSENTINEL.

Defines immutable sequential evidence state, session processing outcome enums,
provenance contracts, and decision status including Phase 6C calibrated threshold & horizon exhaustion.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any
from qsentinel_monitor.quantum_evidence.models import CalibratedStage1Decision, CalibratedDecisionStatus


class SessionProcessingOutcome(str, Enum):
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    DUPLICATE_SESSION = "DUPLICATE_SESSION"
    OUT_OF_ORDER_SESSION = "OUT_OF_ORDER_SESSION"
    INCOMPATIBLE_PROVENANCE = "INCOMPATIBLE_PROVENANCE"
    UNAVAILABLE_CALIBRATION = "UNAVAILABLE_CALIBRATION"
    UNAVAILABLE_STAGE1 = "UNAVAILABLE_STAGE1"
    INVALID_NUMERICAL_INPUT = "INVALID_NUMERICAL_INPUT"
    HORIZON_EXCEEDED = "HORIZON_EXCEEDED"


class SequentialDecisionStatus(str, Enum):
    SEQUENTIAL_NOMINAL = "SEQUENTIAL_NOMINAL"
    SEQUENTIAL_EVIDENCE_ELEVATED = "SEQUENTIAL_EVIDENCE_ELEVATED"
    SEQUENTIAL_UNINITIALIZED = "SEQUENTIAL_UNINITIALIZED"
    SEQUENTIAL_PROVENANCE_MISMATCH = "SEQUENTIAL_PROVENANCE_MISMATCH"
    SEQUENTIAL_UNCALIBRATED = "SEQUENTIAL_UNCALIBRATED"
    SEQUENTIAL_HORIZON_EXCEEDED = "SEQUENTIAL_HORIZON_EXCEEDED"


@dataclass(frozen=True)
class ProvenanceIdentity:
    artifact_content_hash: str
    artifact_schema_version: str
    architecture_version: str
    stage1_model_version: str


@dataclass(frozen=True)
class SequentialEvidenceState:
    """
    Immutable state tracking sequential evidence accumulation across sessions.
    Transitions via: previous_state + new_decision -> next_state
    """
    cumulative_evidence: float
    processed_valid_count: int
    skipped_session_count: int
    last_accepted_session_id: str | None
    last_accepted_sequence_number: int
    provenance_identity: ProvenanceIdentity | None
    decision_status: SequentialDecisionStatus
    history_session_ids: tuple[str, ...]


@dataclass(frozen=True)
class SequentialUpdateResult:
    """
    Immutable result of updating sequential evidence state with a CalibratedStage1Decision.
    """
    previous_state: SequentialEvidenceState
    next_state: SequentialEvidenceState
    outcome: SessionProcessingOutcome
    decision_evaluated: CalibratedStage1Decision
    evidence_delta: float
    diagnostic_reason: str
