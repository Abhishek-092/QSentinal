"""
Immutable Domain Models for Phase 7 Attack Evaluation & Metric Aggregation.

Defines per-session ground truth, trial classification state machine outcomes,
aggregated threat metrics, and reproducible EvaluationReport objects.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from experiments.attack_scenarios import AttackScenario, AttackType


class TrialClassification(str, Enum):
    TRUE_DETECTION = "TRUE_DETECTION"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    PRE_ATTACK_FALSE_ALARM = "PRE_ATTACK_FALSE_ALARM"
    HORIZON_EXCEEDED = "HORIZON_EXCEEDED"
    CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"


@dataclass(frozen=True)
class SessionGroundTruth:
    """
    Immutable ground truth recorded for each simulated session.
    """
    session_id: str
    sequence_number: int
    is_attack_present: bool
    attack_type: AttackType
    effective_p_z: float
    effective_p_x: float


@dataclass(frozen=True)
class AttackTrialResult:
    """
    Immutable trial result representing one stream evaluation.
    Enforces exactly ONE terminal classification per trial.
    """
    trial_id: str
    scenario_id: str
    classification: TrialClassification
    first_detection_sequence: Optional[int]
    detection_latency: Optional[int]
    processed_sessions: int
    final_cumulative_glr: float
    stream_seed: int
    session_ground_truths: Tuple[SessionGroundTruth, ...]


@dataclass(frozen=True)
class DetectionMetrics:
    """
    Aggregated statistical detection metrics.
    Includes 95% Wilson score confidence intervals for TPR and FPR.
    """
    n_trials: int
    n_valid_trials: int
    true_positives: int
    false_negatives: int
    false_positives: int
    pre_attack_false_alarms: int
    tpr: Optional[float]
    fpr: Optional[float]
    fnr: Optional[float]
    tpr_ci_95: Tuple[Optional[float], Optional[float]]
    fpr_ci_95: Tuple[Optional[float], Optional[float]]
    mean_latency: Optional[float]
    median_latency: Optional[float]
    horizon_exceeded_count: int
    unavailable_count: int


@dataclass(frozen=True)
class EvaluationReport:
    """
    End-to-end reproducible evaluation report containing scenario configs,
    aggregated detection metrics, trial results, and artifact provenances.
    """
    evaluation_mode: str
    scenarios: Tuple[AttackScenario, ...]
    metrics: DetectionMetrics
    trial_results: Tuple[AttackTrialResult, ...]
    stage1_artifact_provenance: Dict[str, Any]
    stage2_artifact_provenance: Dict[str, Any]
    seed_provenance: Dict[str, Any]
    statistical_limitation_notice: str
