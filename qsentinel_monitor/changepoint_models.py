"""
Phase 8 Change-Point (Offset GLR-CUSUM) Data Models & State Contracts for QSENTINEL.

Defines immutable change-point state models, decision statuses, processing outcomes,
provenance identities, stream calibration contexts, and calibrated decision contracts.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ChangePointProcessingOutcome(str, Enum):
    EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
    DUPLICATE_SESSION = "DUPLICATE_SESSION"
    OUT_OF_ORDER_SESSION = "OUT_OF_ORDER_SESSION"
    INCOMPATIBLE_PROVENANCE = "INCOMPATIBLE_PROVENANCE"
    UNAVAILABLE_INPUT = "UNAVAILABLE_INPUT"
    INVALID_NUMERICAL_INPUT = "INVALID_NUMERICAL_INPUT"
    CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"
    OUT_OF_SUPPORT = "OUT_OF_SUPPORT"
    HORIZON_EXCEEDED = "HORIZON_EXCEEDED"


class ChangePointDecisionStatus(str, Enum):
    CHANGEPOINT_UNINITIALIZED = "CHANGEPOINT_UNINITIALIZED"
    CHANGEPOINT_CALIBRATED_NOMINAL = "CHANGEPOINT_CALIBRATED_NOMINAL"
    CHANGEPOINT_CALIBRATED_ELEVATED = "CHANGEPOINT_CALIBRATED_ELEVATED"
    CHANGEPOINT_UNAVAILABLE = "CHANGEPOINT_UNAVAILABLE"
    CHANGEPOINT_OUT_OF_SUPPORT = "CHANGEPOINT_OUT_OF_SUPPORT"
    CHANGEPOINT_PROVENANCE_MISMATCH = "CHANGEPOINT_PROVENANCE_MISMATCH"
    CHANGEPOINT_CALIBRATION_UNAVAILABLE = "CHANGEPOINT_CALIBRATION_UNAVAILABLE"
    CHANGEPOINT_HORIZON_EXCEEDED = "CHANGEPOINT_HORIZON_EXCEEDED"


@dataclass(frozen=True)
class ChangePointProvenanceIdentity:
    artifact_content_hash: str
    artifact_schema_version: str
    architecture_version: str
    stage1_model_version: str
    changepoint_model_version: str


@dataclass(frozen=True)
class StreamChangePointContext:
    calibration_p: float
    horizon_sessions: int
    artifact_content_hash: str
    calibration_guarantee: str  # "HORIZON_BOUNDED"


@dataclass(frozen=True)
class ChangePointTestState:
    cusum_statistic: float
    active_run_length: int
    estimated_excursion_onset: int | None
    processed_valid_count: int
    skipped_session_count: int
    last_accepted_session_id: str | None
    last_accepted_sequence_number: int
    provenance_identity: ChangePointProvenanceIdentity | None
    decision_status: ChangePointDecisionStatus
    history_session_ids: tuple[str, ...]
    calibration_context: StreamChangePointContext | None = None


@dataclass(frozen=True)
class ChangePointUpdateResult:
    previous_state: ChangePointTestState
    next_state: ChangePointTestState
    outcome: ChangePointProcessingOutcome
    session_id: str
    sequence_number: int
    session_log_likelihood_ratio: float
    applied_null_offset: float | None
    applied_threshold: float | None
    active_run_length: int
    estimated_excursion_onset: int | None
    diagnostic_reason: str


@dataclass(frozen=True)
class CalibratedChangePointDecision:
    session_id: str
    sequence_number: int
    cusum_statistic: float
    active_run_length: int
    estimated_excursion_onset: int | None
    processed_valid_count: int
    calibration_p: float
    matched_calibration_p: float | None
    null_offset_d: float | None
    empirical_critical_value: float | None
    horizon_sessions: int
    decision_status: ChangePointDecisionStatus
    outcome: ChangePointProcessingOutcome
    artifact_content_hash: str
    artifact_schema_version: str
    architecture_version: str
    changepoint_model_version: str
    calibration_guarantee: str  # "HORIZON_BOUNDED"
    diagnostic_reason: str
