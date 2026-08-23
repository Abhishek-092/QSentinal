"""
Domain models for QSENTINEL quantum evidence collection, Stage 1 monitoring, and calibrated decision contracts.
All domain objects use deeply immutable dataclasses with tuples.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from qds.transcript import ProtocolDecision, SessionTranscript


class CalibrationLookupStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    DEGENERATE_BOUNDARY = "DEGENERATE_BOUNDARY"
    CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"
    CALIBRATION_OUT_OF_SUPPORT = "CALIBRATION_OUT_OF_SUPPORT"
    STAGE1_UNAVAILABLE = "STAGE1_UNAVAILABLE"


class CalibratedDecisionStatus(str, Enum):
    MODEL_CONSISTENT = "MODEL_CONSISTENT"
    MODEL_INCONSISTENT = "MODEL_INCONSISTENT"
    DEGENERATE_BOUNDARY = "DEGENERATE_BOUNDARY"
    CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"
    CALIBRATION_OUT_OF_SUPPORT = "CALIBRATION_OUT_OF_SUPPORT"
    STAGE1_UNAVAILABLE = "STAGE1_UNAVAILABLE"


@dataclass(frozen=True)
class CalibratedStage1Decision:
    """
    Immutable result of applying a verified offline CalibrationArtifact to a Stage1Result.
    Preserves full artifact provenance for end-to-end auditability.
    """
    session_id: str
    raw_statistic_t: float
    fitted_p_hat: float

    lookup_status: CalibrationLookupStatus
    decision: CalibratedDecisionStatus

    matched_calibration_p: Optional[float]

    empirical_critical_value: Optional[float]
    asymptotic_critical_value: Optional[float]

    margin_to_critical_value: Optional[float]

    artifact_content_hash: str
    artifact_schema_version: str
    architecture_version: str
    stage1_model_version: str

    diagnostic_reason: str


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

    @property
    def mismatch_rate(self) -> float:
        return self.overall_mismatch_rate

    @property
    def correlation(self) -> float:
        return 1.0 - 2.0 * self.overall_mismatch_rate

    @property
    def entropy(self) -> float:
        p = self.overall_mismatch_rate
        if p <= 0 or p >= 1:
            return 0.0
        import math
        return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))

    @property
    def pauli_consistency(self) -> float:
        return max(0.0, 1.0 - 2.0 * self.overall_mismatch_rate)



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

    @property
    def p_hat(self) -> float:
        return self.best_fit_p

    @property
    def ll_ratio(self) -> float:
        return self.statistic

    @property
    def passed(self) -> bool:
        return self.status == "PROCESSED" and self.statistic < 3.841

    @property
    def details(self) -> str:
        return f"Stage 1 status={self.status}, T={self.statistic:.4f}, p_hat={self.best_fit_p:.4f}"

    @property
    def optimizer_converged(self) -> bool:
        return self.optimization_success



@dataclass(frozen=True)
class MonitoringResult:
    """
    Advisory monitoring decision combining evidence, Stage 1 results, and optional calibrated decision.
    Guaranteed strictly advisory: never mutates or overrides ProtocolDecision.
    """
    session_id: str
    protocol_decision: ProtocolDecision
    monitoring_status: str  # e.g., "MONITORED_ADVISORY"
    evidence: QuantumEvidence
    stage1_result: Stage1Result
    calibrated_decision: Optional[CalibratedStage1Decision] = None
    is_advisory: bool = True
