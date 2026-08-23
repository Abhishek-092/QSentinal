"""
Stage 2 Joint Sequential Likelihood Test Domain Models & State Contracts for QSENTINEL.

Defines immutable Stage 2 sequential decision status, processing outcomes,
provenance identity, test state, and update results.
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


class Stage2ProcessingOutcome(str, Enum):
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    DUPLICATE_SESSION = "DUPLICATE_SESSION"
    OUT_OF_ORDER_SESSION = "OUT_OF_ORDER_SESSION"
    INCOMPATIBLE_PROVENANCE = "INCOMPATIBLE_PROVENANCE"
    UNAVAILABLE_INPUT = "UNAVAILABLE_INPUT"
    INVALID_NUMERICAL_INPUT = "INVALID_NUMERICAL_INPUT"


@dataclass(frozen=True)
class Stage2ProvenanceIdentity:
    """
    Immutable provenance identity for Stage 2 sequential likelihood testing.
    Can be tied to Stage 1 artifact provenance or monitor pipeline model versions.
    """
    artifact_content_hash: str
    artifact_schema_version: str
    architecture_version: str
    stage1_model_version: str
    stage2_model_version: str = "v1.0"


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
