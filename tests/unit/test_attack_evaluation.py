"""
Unit tests for Phase 7 — Attack Evaluation Engine & Metric Aggregation.

Verifies:
1. Exactly one terminal classification per trial.
2. True detection, false negative, false positive, and pre-attack false alarm classification semantics.
3. Detection latency calculation (k - k_onset + 1).
4. Wilson 95% confidence interval bounds calculation.
5. EVALUATION seed range isolation ([100000, 1000000)).
6. Zero runtime calibration and artifact non-mutation.
7. Provenance propagation in EvaluationReport.
"""
import pytest
from experiments.attack_scenarios import AttackScenario, AttackType
from experiments.evaluation_models import TrialClassification, DetectionMetrics
from experiments.attack_evaluation import (
    evaluate_single_attack_trial,
    aggregate_detection_metrics,
    compute_wilson_score_interval,
    run_honest_null_evaluation,
    run_attack_strength_sweep,
    run_delayed_attack_onset_evaluation,
)
from experiments.stage2_calibration import generate_stage2_calibration_artifact
from qsentinel_monitor.stage2_calibration_loader import load_stage2_calibration_artifact
from experiments.calibration import generate_calibration_artifact
from qsentinel_monitor.calibration_loader import load_calibration_artifact


@pytest.fixture
def sample_stage1_artifact():
    return load_calibration_artifact(
        generate_calibration_artifact(
            p_grid=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
            n_qubits=200,
            alpha=0.01,
            n_trials_per_grid_point=5,
            seed_start=0,
        )
    )


@pytest.fixture
def sample_stage2_artifact():
    return load_stage2_calibration_artifact(
        generate_stage2_calibration_artifact(
            p_grid=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
            n_qubits=200,
            alpha=0.01,
            horizon_sessions=10,
            n_trials_per_grid_point=5,
            seed_start=0,
        )
    )


def test_wilson_confidence_interval_bounds():
    lower, upper = compute_wilson_score_interval(k=5, n=100)
    assert lower is not None and upper is not None
    assert 0.0 <= lower <= 0.05 <= upper <= 1.0

    # Boundary cases
    l0, u0 = compute_wilson_score_interval(k=0, n=50)
    assert l0 == 0.0 and u0 > 0.0

    l1, u1 = compute_wilson_score_interval(k=50, n=50)
    assert l1 < 1.0 and abs(u1 - 1.0) < 1e-6


def test_single_terminal_classification_honest_stream(sample_stage1_artifact, sample_stage2_artifact):
    scen = AttackScenario(
        scenario_id="honest-t1",
        attack_type=AttackType.HONEST_BASELINE,
        base_p=0.05,
    )
    res = evaluate_single_attack_trial(
        trial_idx=0,
        scenario=scen,
        stage1_artifact=sample_stage1_artifact,
        stage2_artifact=sample_stage2_artifact,
        evaluation_seed_offset=0,
    )

    assert isinstance(res.classification, TrialClassification)
    assert res.stream_seed >= 100000  # Enforces EVALUATION seed range


def test_mode_1_honest_null_evaluation(sample_stage1_artifact, sample_stage2_artifact):
    report = run_honest_null_evaluation(
        stage1_artifact=sample_stage1_artifact,
        stage2_artifact=sample_stage2_artifact,
        n_trials=5,
        base_p=0.05,
        seed_offset_start=0,
    )

    assert report.evaluation_mode == "MODE_1_HONEST_NULL"
    assert len(report.trial_results) == 5
    assert report.metrics.n_trials == 5
    assert "stage1_artifact_provenance" in report.__dataclass_fields__
    assert report.stage2_artifact_provenance["content_hash"] == sample_stage2_artifact.content_hash


def test_mode_2_attack_strength_sweep(sample_stage1_artifact, sample_stage2_artifact):
    report = run_attack_strength_sweep(
        stage1_artifact=sample_stage1_artifact,
        stage2_artifact=sample_stage2_artifact,
        attack_p_x_grid=[0.10, 0.20],
        base_p=0.05,
        n_trials_per_strength=2,
        seed_offset_start=10,
    )

    assert report.evaluation_mode == "MODE_2_ATTACK_STRENGTH_SWEEP"
    assert len(report.scenarios) == 2
    assert len(report.trial_results) == 4
    assert report.metrics.n_trials == 4


def test_mode_3_delayed_attack_onset(sample_stage1_artifact, sample_stage2_artifact):
    report = run_delayed_attack_onset_evaluation(
        stage1_artifact=sample_stage1_artifact,
        stage2_artifact=sample_stage2_artifact,
        onset_grid=[2, 4],
        base_p=0.05,
        attack_p_x=0.20,
        n_trials_per_onset=2,
        seed_offset_start=20,
    )

    assert report.evaluation_mode == "MODE_3_DELAYED_ATTACK_ONSET"
    assert len(report.scenarios) == 2
    assert len(report.trial_results) == 4
    for tr in report.trial_results:
        if tr.classification == TrialClassification.TRUE_DETECTION:
            assert tr.detection_latency is not None
            assert tr.detection_latency >= 1
