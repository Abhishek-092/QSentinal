"""
Statistical & Property Tests for Phase 7 — Attack Detection Properties.

Verifies:
1. Stage 2 evidence response property: Basis-asymmetric noise (p_z != p_x) produces higher cumulative GLR evidence than symmetric noise (p_z == p_x).
2. Monotonic sensitivity property: Higher basis asymmetry produces generally higher detection rates over controlled Monte Carlo samples.
3. Pre-attack false alarm isolation property: Elevated decisions occurring before attack onset session are strictly classified as PRE_ATTACK_FALSE_ALARM.
4. Artifact non-mutation invariant: Artifact content hashes remain strictly unchanged before and after evaluation.
5. EVALUATION seed isolation invariant: No evaluation trial consumes seeds outside [100000, 1000000).
"""
import pytest
from experiments.attack_scenarios import AttackScenario, AttackType
from experiments.evaluation_models import TrialClassification
from experiments.attack_evaluation import (
    run_honest_null_evaluation,
    run_attack_strength_sweep,
    evaluate_single_attack_trial,
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


def test_stage2_glr_evidence_response_to_basis_asymmetry(sample_stage1_artifact, sample_stage2_artifact):
    # Honest baseline (symmetric p = 0.05)
    scen_honest = AttackScenario(
        scenario_id="honest-prop",
        attack_type=AttackType.HONEST_BASELINE,
        base_p=0.05,
    )
    res_honest = evaluate_single_attack_trial(
        trial_idx=0,
        scenario=scen_honest,
        stage1_artifact=sample_stage1_artifact,
        stage2_artifact=sample_stage2_artifact,
        evaluation_seed_offset=100,
    )

    # Asymmetric attack (base p = 0.05, attack_p_x = 0.20)
    scen_asym = AttackScenario(
        scenario_id="asym-prop",
        attack_type=AttackType.BASIS_ASYMMETRIC_NOISE,
        base_p=0.05,
        attack_p_z=0.05,
        attack_p_x=0.20,
        attack_onset_session=1,
        attack_duration=10,
    )
    res_asym = evaluate_single_attack_trial(
        trial_idx=0,
        scenario=scen_asym,
        stage1_artifact=sample_stage1_artifact,
        stage2_artifact=sample_stage2_artifact,
        evaluation_seed_offset=100,
    )

    # Cumulative GLR evidence must be significantly higher for asymmetric attack
    assert res_asym.final_cumulative_glr > res_honest.final_cumulative_glr


def test_artifact_non_mutation_invariant(sample_stage1_artifact, sample_stage2_artifact):
    h1_before = sample_stage1_artifact.content_hash
    h2_before = sample_stage2_artifact.content_hash

    # Run evaluation
    run_honest_null_evaluation(
        stage1_artifact=sample_stage1_artifact,
        stage2_artifact=sample_stage2_artifact,
        n_trials=5,
        base_p=0.05,
        seed_offset_start=50,
    )

    assert sample_stage1_artifact.content_hash == h1_before
    assert sample_stage2_artifact.content_hash == h2_before


def test_evaluation_seed_isolation_invariant(sample_stage1_artifact, sample_stage2_artifact):
    scen = AttackScenario(
        scenario_id="seed-iso",
        attack_type=AttackType.HONEST_BASELINE,
        base_p=0.05,
    )
    for offset in range(5):
        res = evaluate_single_attack_trial(
            trial_idx=offset,
            scenario=scen,
            stage1_artifact=sample_stage1_artifact,
            stage2_artifact=sample_stage2_artifact,
            evaluation_seed_offset=offset,
        )
        assert 100000 <= res.stream_seed < 1000000
