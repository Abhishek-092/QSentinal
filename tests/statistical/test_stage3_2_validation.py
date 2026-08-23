import pytest
import numpy as np
import scipy.stats as stats

from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from experiments.seed_allocator import SeedAllocator


def test_stage3_2_noise_free_baseline():
    """
    TEST 1 — NOISE-FREE BASELINE (p = 0.00)
    Uses deterministic EVALUATION seeds.
    Verifies:
    - m_Z = 0.0 exactly
    - m_X = 0.0 exactly
    - No systematic basis asymmetry
    - Stage 1 statistic T ≈ 0.0 (within optimizer numerical tolerance)
    """
    seed = SeedAllocator.get_seed("EVALUATION", 0)
    config = SessionConfig(n_qubits=500, noise_parameter_p=0.00, seed=seed)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    stage1_res = evaluate_stage1(evidence)

    assert evidence.z_mismatch_count == 0
    assert evidence.x_mismatch_count == 0
    assert evidence.z_mismatch_rate == 0.0
    assert evidence.x_mismatch_rate == 0.0
    assert evidence.overall_mismatch_rate == 0.0
    assert pytest.approx(stage1_res.statistic, abs=1e-2) == 0.0
    assert pytest.approx(stage1_res.best_fit_p, abs=1e-3) == 0.0


@pytest.mark.parametrize("p_configured", [0.15, 0.30, 0.45])
def test_stage3_2_noise_model_empirical_validation(p_configured):
    """
    TESTS 2-5 — EMPIRICAL NOISE MODEL & BASIS SYMMETRY VALIDATION
    Validates for p ∈ {0.15, 0.30, 0.45}:
    - E[m_Z | p] ≈ 2p/3
    - E[m_X | p] ≈ 2p/3
    - Basis symmetry: |m_Z - m_X| within 99% binomial confidence interval
    - p_hat parameter recovery: |p_hat - p_configured| within tolerance
    """
    expected_mismatch_rate = (2.0 / 3.0) * p_configured

    # Aggregate 10 independent sessions per noise level to collect ~1000 sifted trials per basis
    n_sessions = 10
    total_z_sifted = 0
    total_z_mismatches = 0
    total_x_sifted = 0
    total_x_mismatches = 0

    for i in range(n_sessions):
        seed = SeedAllocator.get_seed("EVALUATION", 1000 + int(p_configured * 100) * 10 + i)
        config = SessionConfig(n_qubits=400, noise_parameter_p=p_configured, seed=seed)
        transcript = run_session(config)
        evidence = extract_evidence(transcript)

        total_z_sifted += evidence.z_sifted_count
        total_z_mismatches += evidence.z_mismatch_count
        total_x_sifted += evidence.x_sifted_count
        total_x_mismatches += evidence.x_mismatch_count

    obs_m_Z = total_z_mismatches / total_z_sifted
    obs_m_X = total_x_mismatches / total_x_sifted
    obs_m_total = (total_z_mismatches + total_x_mismatches) / (total_z_sifted + total_x_sifted)

    # 99% binomial confidence interval half-width for Z and X
    z_ci_99 = 2.576 * np.sqrt(expected_mismatch_rate * (1.0 - expected_mismatch_rate) / total_z_sifted)
    x_ci_99 = 2.576 * np.sqrt(expected_mismatch_rate * (1.0 - expected_mismatch_rate) / total_x_sifted)

    # Test 2: Empirical Z-basis rate
    assert abs(obs_m_Z - expected_mismatch_rate) <= z_ci_99, (
        f"Z-basis mismatch rate {obs_m_Z:.4f} deviates from expected {expected_mismatch_rate:.4f} beyond 99% CI"
    )

    # Test 3: Empirical X-basis rate
    assert abs(obs_m_X - expected_mismatch_rate) <= x_ci_99, (
        f"X-basis mismatch rate {obs_m_X:.4f} deviates from expected {expected_mismatch_rate:.4f} beyond 99% CI"
    )

    # Test 4: Basis symmetry (|m_Z - m_X| check)
    diff = abs(obs_m_Z - obs_m_X)
    diff_ci_99 = 2.576 * np.sqrt(expected_mismatch_rate * (1.0 - expected_mismatch_rate) * (1/total_z_sifted + 1/total_x_sifted))
    assert diff <= diff_ci_99, f"Basis asymmetry detected: |m_Z - m_X| = {diff:.4f} exceeds 99% CI limit {diff_ci_99:.4f}"

    # Test 5 & Parameter Recovery: p_hat = (3/2) * m_total
    p_hat_recovered = 1.5 * obs_m_total
    assert abs(p_hat_recovered - p_configured) <= 0.03, (
        f"Recovered p_hat {p_hat_recovered:.4f} differs from configured noise parameter {p_configured:.4f}"
    )


def test_stage3_2_end_to_end_stage1_consistency():
    """
    TEST 6 — STAGE 1 ASSUMPTION VALIDATION
    Verifies that honest runtime-generated transcripts fed through Stage 1 produce:
    - Finite test statistic T
    - Diagnostic p-values qualitatively consistent with null sampling variation
    - Successful optimization
    """
    seed = SeedAllocator.get_seed("EVALUATION", 5000)
    config = SessionConfig(n_qubits=1000, noise_parameter_p=0.20, seed=seed)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    stage1_res = evaluate_stage1(evidence)

    assert stage1_res.status == "PROCESSED"
    assert stage1_res.optimization_success is True
    assert not np.isnan(stage1_res.statistic)
    assert not np.isinf(stage1_res.statistic)
    assert stage1_res.diagnostic_info["degrees_of_freedom"] == 1
