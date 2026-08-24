"""HTTP request/response schemas for the API layer."""
from typing import Any
from pydantic import BaseModel, Field


# --- Common & Error Schemas ---

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str = "ready"
    database_status: str = "connected"


# --- Stream Schemas ---

class StreamCreateRequest(BaseModel):
    stream_id: str = Field(..., json_schema_extra={"example": "stream-sender-recipient-01"})
    description: str | None = Field("", json_schema_extra={"example": "QDS Channel between sender and recipient"})


class StreamResponse(BaseModel):
    stream_id: str
    description: str
    created_at: str
    status: str


# --- Epoch Schemas ---

class EpochCreateRequest(BaseModel):
    calibration_p: float = Field(0.02, json_schema_extra={"example": 0.02}, description="Explicit channel noise operating point")
    additional_context: dict[str, Any | None] = Field(default_factory=dict)


class EpochResponse(BaseModel):
    epoch_id: str
    stream_id: str
    epoch_index: int
    status: str
    termination_reason: str | None = None
    stage1_artifact_hash: str | None = None
    stage2_artifact_hash: str | None = None
    changepoint_artifact_hash: str | None = None
    calibration_context: dict[str, Any]
    created_at: str
    closed_at: str | None = None


class EpochRenewRequest(BaseModel):
    calibration_p: float = Field(0.02, json_schema_extra={"example": 0.02})
    termination_reason: str | None = Field("EXPLICIT_RENEWAL")
    additional_context: dict[str, Any | None] = Field(default_factory=dict)


# --- Session Submission Schemas ---

class ProtocolDecisionSchema(BaseModel):
    accepted: bool
    reason: str
    mismatch_count: int
    sifted_length: int
    s_a: int
    s_v: float
    session_id: str


class SessionTranscriptSchema(BaseModel):
    session_id: str
    timestamp: float
    sender_id: str
    recipient_id: str
    auth_token: str
    nonce: str
    message_bit: int
    keys: list[int]
    bases: list[int]
    recipient_bases: list[int]
    bell_outcomes: list[list[int]]
    raw_measurements: list[int]
    sifted_indices: list[int]
    mismatch_flags: list[bool]
    pauli_corrections_applied: list[list[int]]
    protocol_decision: ProtocolDecisionSchema
    metadata: dict[str, Any | None] = Field(default_factory=dict)


class SessionSubmissionRequest(BaseModel):
    transcript: SessionTranscriptSchema


# --- Monitoring & Threat Response Schemas ---

class QuantumEvidenceSchema(BaseModel):
    session_id: str
    sample_count: int
    total_sifted_count: int
    total_mismatch_count: int
    overall_mismatch_rate: float
    z_sifted_count: int
    z_mismatch_count: int
    z_mismatch_rate: float
    x_sifted_count: int
    x_mismatch_count: int
    x_mismatch_rate: float


class Stage1ResultSchema(BaseModel):
    session_id: str
    status: str
    best_fit_p: float
    statistic: float
    uncalibrated_theoretical_p_value: float | None = None
    optimization_success: bool


class ProvenanceBundleSchema(BaseModel):
    stage1_artifact_hash: str | None = None
    stage2_artifact_hash: str | None = None
    changepoint_artifact_hash: str | None = None
    architecture_version: str = "v9.0"


class UnifiedThreatAssessmentSchema(BaseModel):
    session_id: str
    sequence_number: int
    security_posture: str
    threat_severity: str
    contributing_detectors: list[str]
    explanation: str
    estimated_excursion_onset: int | None = None
    stage2_horizon_exceeded: bool
    changepoint_horizon_exceeded: bool
    provenance_bundle: ProvenanceBundleSchema


class UnifiedMonitoringResultSchema(BaseModel):
    session_id: str
    sequence_number: int
    protocol_decision: ProtocolDecisionSchema
    evidence: QuantumEvidenceSchema
    stage1_result: Stage1ResultSchema
    threat_assessment: UnifiedThreatAssessmentSchema
    is_advisory: bool = True


class MonitoringStateResponseSchema(BaseModel):
    epoch_id: str
    sequence_number: int
    epoch_status: str
    stage2_processed_count: int
    stage2_decision_status: str
    stage2_cumulative_glr: float
    changepoint_processed_count: int
    changepoint_decision_status: str
    changepoint_cusum_statistic: float
    changepoint_active_run_length: int
    changepoint_estimated_onset: int | None = None
