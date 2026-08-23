"""
Domain models for QSENTINEL quantum evidence collection and Stage 1 monitoring.
All domain objects are frozen immutable dataclasses to prevent post-finalization state mutations.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from qds.transcript import ProtocolDecision, SessionTranscript


@dataclass(frozen=True)
class QuantumEvidence:
    """
    Strongly-typed immutable quantum evidence derived post-session from SessionTranscript.
    Quantum evidence vector:
    - 2 independent dimensions: refined channel parameter p̂ (derived from mutual consistency of m, C, H)
      and pauli_correction_consistency.
    """
    session_id: str
    sample_count: int
    sifted_count: int
    mismatch_count: int
    mismatch_rate: float
    correlation: float
    entropy: float
    pauli_correction_consistency: float
    raw_evidence_summary: Dict[str, Any]


@dataclass(frozen=True)
class Stage1Result:
    """
    Immutable result of Stage 1 profile-likelihood mutual-consistency test.
    Tests H0: Observed (m, C, H) are jointly consistent with a single scalar depolarizing noise parameter p ∈ [0, 0.5].
    """
    session_id: str
    status: str  # "MODEL_VALID", "MODEL_INVALID", or "OPTIMIZER_FAILURE"
    model_valid: bool
    best_fit_p: float
    statistic: float  # Profile-likelihood ratio test statistic T
    p_value: Optional[float]
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
    monitoring_status: str  # e.g., "ACCEPTED_ADVISORY", "FLAGGED_MODEL_INVALID"
    evidence: QuantumEvidence
    stage1_result: Stage1Result
    is_advisory: bool = True
