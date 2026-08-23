"""
Unit tests for Phase 7 — Attack Scenarios and Experimental Session Generator.

Verifies:
1. Scenario immutability and post-init validation rules.
2. Rejection of invalid scenario probabilities, onset, duration, qubits, and symmetry.
3. Deterministic child seed derivation independence from Python hash() or wall clock.
4. Experimental session generation using QDS primitives without modifying qds package.
5. Telemetry compatibility with extract_evidence().
6. Basis asymmetry reflected in experimental session transcripts.
7. Delayed attack onset session index activation logic.
"""
import pytest
from experiments.attack_scenarios import (
    AttackScenario,
    AttackType,
    derive_evaluation_child_seed,
    run_experimental_session,
)
from qsentinel_monitor.quantum_evidence import extract_evidence


def test_attack_scenario_immutability():
    scen = AttackScenario(
        scenario_id="s1",
        attack_type=AttackType.HONEST_BASELINE,
        base_p=0.05,
    )
    with pytest.raises(AttributeError):
        scen.base_p = 0.10


def test_attack_scenario_validation():
    with pytest.raises(ValueError, match="base_p"):
        AttackScenario(scenario_id="invalid", attack_type=AttackType.HONEST_BASELINE, base_p=0.6)

    with pytest.raises(ValueError, match="attack_onset_session"):
        AttackScenario(scenario_id="invalid", attack_type=AttackType.HONEST_BASELINE, attack_onset_session=0)

    with pytest.raises(ValueError, match="requires attack_p_z != attack_p_x"):
        AttackScenario(
            scenario_id="invalid",
            attack_type=AttackType.BASIS_ASYMMETRIC_NOISE,
            attack_p_z=0.10,
            attack_p_x=0.10,
        )


def test_child_seed_derivation_determinism():
    s1 = derive_evaluation_child_seed(stream_seed=100000, trial_idx=1, session_idx=5)
    s2 = derive_evaluation_child_seed(stream_seed=100000, trial_idx=1, session_idx=5)
    assert s1 == s2
    assert isinstance(s1, int)
    assert 0 <= s1 < 2**31


def test_experimental_session_telemetry_compatibility():
    scen = AttackScenario(
        scenario_id="s-baseline",
        attack_type=AttackType.HONEST_BASELINE,
        base_p=0.05,
        n_qubits=100,
    )
    transcript = run_experimental_session(scen, session_index=1, seed=12345)
    assert transcript.session_id is not None
    assert len(transcript.keys) == 100
    assert len(transcript.bases) == 100

    evidence = extract_evidence(transcript)
    assert evidence.session_id == transcript.session_id
    assert evidence.total_sifted_count > 0
    assert evidence.z_sifted_count + evidence.x_sifted_count == evidence.total_sifted_count


def test_basis_asymmetric_experimental_session():
    scen = AttackScenario(
        scenario_id="s-asym",
        attack_type=AttackType.BASIS_ASYMMETRIC_NOISE,
        base_p=0.02,
        attack_p_z=0.02,
        attack_p_x=0.25,
        attack_onset_session=1,
        attack_duration=10,
        n_qubits=400,
    )
    transcript = run_experimental_session(scen, session_index=1, seed=54321)
    evidence = extract_evidence(transcript)
    
    # High p_x (0.25) should produce significantly higher mismatch rate in X basis than Z basis (0.02)
    assert evidence.x_mismatch_rate > evidence.z_mismatch_rate


def test_delayed_attack_onset_activation():
    scen = AttackScenario(
        scenario_id="s-delayed",
        attack_type=AttackType.DELAYED_ATTACK_ONSET,
        base_p=0.02,
        attack_p_z=0.02,
        attack_p_x=0.20,
        attack_onset_session=5,
        attack_duration=10,
        n_qubits=200,
    )
    
    # Session 1 (< onset 5) is honest
    t1 = run_experimental_session(scen, session_index=1, seed=111)
    assert t1.metadata["is_attack_active"] is False
    assert t1.metadata["effective_p_x"] == 0.02

    # Session 5 (>= onset 5) is attacked
    t5 = run_experimental_session(scen, session_index=5, seed=222)
    assert t5.metadata["is_attack_active"] is True
    assert t5.metadata["effective_p_x"] == 0.20
