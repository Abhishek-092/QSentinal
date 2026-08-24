"""
Experiment configuration dataclasses for QSENTINEL evaluation.

Defines attack conditions, experiment configurations, and the standard 7-condition test suite
as specified in the frozen architecture (Section 12, F8).
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AttackCondition:
    """A single attack condition for Monte Carlo evaluation."""
    name: str
    strategy: str  # maps to attacks.strategies ATTACK_REGISTRY key, or "honest"
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    # Detection path (for ablation analysis)
    primary_detector: str = "stage2"  # "fsm", "stage2", "cusum", "protocol"


@dataclass(frozen=True)
class ExperimentConfig:
    """Configuration for a Monte Carlo experiment run."""
    name: str
    category: str  # "CALIBRATION" | "VALIDATION" | "EVALUATION"
    n_trials_per_condition: int = 1000
    n_qubits: int = 200
    noise_p: float = 0.02
    conditions: tuple[AttackCondition, ...] = ()
    seed_range: tuple[int, int] = (0, 50_000)
    alpha_system: float = 0.01


# Standard 7 conditions per architecture Section 12 / F8
STANDARD_CONDITIONS: tuple[AttackCondition, ...] = (
    AttackCondition(
        name="honest",
        strategy="honest",
        description="No attack — legitimate execution under honest noise",
        primary_detector="protocol",
    ),
    AttackCondition(
        name="clean_forgery",
        strategy="clean_forgery",
        description="Forge |0⟩ instead of authorized R_y(θ)|0⟩",
        primary_detector="protocol",
    ),
    AttackCondition(
        name="sub_threshold_forgery",
        strategy="sub_threshold_forgery",
        description="Small Bloch-angle offset plus extra depolarizing drift",
        primary_detector="stage2",
    ),
    AttackCondition(
        name="channel_manipulation",
        strategy="channel_manipulation",
        description="Strong depolarizing channel on quantum link (p+0.20)",
        primary_detector="stage2",
    ),
    AttackCondition(
        name="low_and_slow_drift",
        strategy="low_and_slow_drift",
        description="Persistent extra depolarizing p≈0.025 — CUSUM detection class",
        primary_detector="cusum",
    ),
    AttackCondition(
        name="replay",
        strategy="replay",
        description="Reuse product state with no fresh EPR pair",
        primary_detector="fsm",
    ),
    AttackCondition(
        name="unauthorized_verification",
        strategy="unauthorized_verification",
        description="Skip Pauli correction — 7th condition (F8)",
        primary_detector="fsm",
    ),
)


# Detection path labels for ablation analysis
DETECTION_PATHS = ("fsm", "stage1", "stage2", "cusum", "attribution")
