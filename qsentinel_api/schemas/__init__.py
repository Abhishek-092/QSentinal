"""
Phase 11 Pydantic API Schemas for QSENTINEL.

Defines HTTP Request & Response schemas separating external API interfaces from internal domain dataclasses.
"""
from typing import Optional, List, Dict, Any, Tuple
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
    stream_id: str = Field(..., example="stream-alice-bob-01")
    description: Optional[str] = Field("", example="QDS Channel between Alice and Bob")


class StreamResponse(BaseModel):
    stream_id: str
    description: str
    created_at: str
    status: str


# --- Epoch Schemas ---

class EpochCreateRequest(BaseModel):
    calibration_p: float = Field(0.02, example=0.02, description="Explicit channel noise operating point")
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EpochResponse(BaseModel):
    epoch_id: str
    stream_id: str
    epoch_index: int
    status: str
    termination_reason: Optional[str] = None
    stage1_artifact_hash: Optional[str] = None
    stage2_artifact_hash: Optional[str] = None
    changepoint_artifact_hash: Optional[str] = None
    calibration_context: Dict[str, Any]
    created_at: str
    closed_at: Optional[str] = None


class EpochRenewRequest(BaseModel):
    calibration_p: float = Field(0.02, example=0.02)
    termination_reason: Optional[str] = Field("EXPLICIT_RENEWAL")
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)


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
    keys: List[int]
    bases: List[int]
    recipient_bases: List[int]
    bell_outcomes: List[List[int]]
    raw_measurements: List[int]
    sifted_indices: List[int]
    mismatch_flags: List[bool]
    pauli_corrections_applied: List[List[int]]
    protocol_decision: ProtocolDecisionSchema
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


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
    uncalibrated_theoretical_p_value: Optional[float] = None
    optimization_success: bool


class ProvenanceBundleSchema(BaseModel):
    stage1_artifact_hash: Optional[str] = None
    stage2_artifact_hash: Optional[str] = None
    changepoint_artifact_hash: Optional[str] = None
    architecture_version: str = "v9.0"


class UnifiedThreatAssessmentSchema(BaseModel):
    session_id: str
    sequence_number: int
    security_posture: str
    threat_severity: str
    contributing_detectors: List[str]
    explanation: str
    estimated_excursion_onset: Optional[int] = None
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
    changepoint_estimated_onset: Optional[int] = None
