"""
Domain models for QSENTINEL quantum evidence collection and Stage 1 monitoring.
All domain objects use deeply immutable dataclasses with tuples.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from qds.transcript import ProtocolDecision, SessionTranscript


@dataclass(frozen=True)
class QuantumEvidence:
    """
    Strongly-typed immutable quantum evidence derived post-session from SessionTranscript.
    Contains genuinely independent basis-conditioned observations:
    - z_sifted_count, z_mismatch_count, z_mismatch_rate (m_Z)
    - x_sifted_count, x_mismatch_count, x_mismatch_rate (m_X)
    - total_sifted_count, total_mismatch_count, overall_mismatch_rate (m)
    """
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
    raw_evidence_summary: Dict[str, Any]


@dataclass(frozen=True)
class Stage1Result:
    """
    Immutable result of Stage 1 profile-likelihood mutual-consistency test.
    Tests H0: Basis mismatch rates m_Z and m_X are jointly consistent with a single scalar depolarizing noise parameter p ∈ [0, 0.5].
    Returns raw statistic T, fitted p_hat, optimization success, and theoretical uncalibrated p-value for diagnostic purposes.
    """
    session_id: str
    status: str  # "PROCESSED" or "OPTIMIZER_FAILURE"
    best_fit_p: float
    statistic: float  # Raw profile-likelihood ratio test statistic T
    uncalibrated_theoretical_p_value: Optional[float]  # Clearly labeled as theoretical / uncalibrated
    optimization_success: bool
    diagnostic_info: Dict[str, Any]


@dataclass(frozen=True)
class MonitoringResult:
    """
    Advisory monitoring decision combining evidence and Stage 1 results.
    Guaranteed strictly advisory: never mutates or overrides ProtocolDecision.
    """
    session_id: str
    protocol_decision: ProtocolDecision
    monitoring_status: str  # e.g., "MONITORED_ADVISORY"
    evidence: QuantumEvidence
    stage1_result: Stage1Result
    is_advisory: bool = True
