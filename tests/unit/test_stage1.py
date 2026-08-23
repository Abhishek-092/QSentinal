import pytest
import numpy as np
from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1, Stage1Result, QuantumEvidence


def test_stage1_honest_noiseless_session():
    """Verify Stage 1 model-fit on zero noise session."""
    config = SessionConfig(n_qubits=100, noise_parameter_p=0.0, seed=42)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    res = evaluate_stage1(evidence)

    assert isinstance(res, Stage1Result)
    assert res.status == "PROCESSED"
    assert pytest.approx(res.best_fit_p, abs=1e-5) == 0.0
    assert pytest.approx(res.statistic, abs=1e-5) == 0.0
    assert res.optimization_success is True


def test_stage1_honest_noise_recovery():
    """Verify Stage 1 accurately recovers best-fit noise parameter p for p=0.06."""
    config = SessionConfig(n_qubits=1000, noise_parameter_p=0.06, seed=777)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    res = evaluate_stage1(evidence)

    assert res.status == "PROCESSED"
    assert res.optimization_success is True
    assert pytest.approx(res.best_fit_p, abs=0.02) == 0.06


def test_stage1_equal_aggregate_mismatch_different_stage1_evidence():
    """
    MANDATORY ADVERSARIAL TEST:
    Constructs two sessions with IDENTICAL total aggregate mismatch counts (k_total = 10 out of n=200),
    but DIFFERENT basis-conditioned distributions:
    - Session A (Symmetric Honest Noise): k_Z = 5, k_X = 5
    - Session B (Asymmetric Channel Attack): k_Z = 10, k_X = 0

    Verifies that:
    1. Overall mismatch rate m is identical (m = 0.05).
    2. Repaired collector produces distinguishable evidence (m_Z != m_X).
    3. Stage 1 likelihood ratio statistic T is materially larger for Session B (Asymmetric attack).
    """
    session_A_evidence = QuantumEvidence(
        session_id="session_A_symmetric",
        sample_count=400,
        total_sifted_count=200,
        total_mismatch_count=10,
        overall_mismatch_rate=0.05,
        z_sifted_count=100,
        z_mismatch_count=5,
        z_mismatch_rate=0.05,
        x_sifted_count=100,
        x_mismatch_count=5,
        x_mismatch_rate=0.05,
        raw_evidence_summary={}
    )

    session_B_evidence = QuantumEvidence(
        session_id="session_B_asymmetric",
        sample_count=400,
        total_sifted_count=200,
        total_mismatch_count=10,
        overall_mismatch_rate=0.05,
        z_sifted_count=100,
        z_mismatch_count=10,
        z_mismatch_rate=0.10,
        x_sifted_count=100,
        x_mismatch_count=0,
        x_mismatch_rate=0.00,
        raw_evidence_summary={}
    )

    res_A = evaluate_stage1(session_A_evidence)
    res_B = evaluate_stage1(session_B_evidence)

    # 1. Total aggregate mismatch is identical
    assert session_A_evidence.overall_mismatch_rate == session_B_evidence.overall_mismatch_rate

    # 2. Fitted p_hat is identical under H0 (p_hat = 1.5 * (10/200) = 0.075)
    assert pytest.approx(res_A.best_fit_p, 1e-4) == res_B.best_fit_p

    # 3. Test statistic T is ~0 for symmetric session A, but materially > 0 for asymmetric session B
    assert pytest.approx(res_A.statistic, abs=1e-5) == 0.0
    assert res_B.statistic > 5.0  # Asymmetric mismatch creates significant likelihood discrepancy!


def test_stage1_degrees_of_freedom_assertion():
    """Verify that Stage 1 diagnostic info asserts 1 degree of freedom."""
    config = SessionConfig(n_qubits=200, noise_parameter_p=0.04, seed=12)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    res = evaluate_stage1(evidence)

    assert res.diagnostic_info["degrees_of_freedom"] == 1
    assert "statistic_T" in res.diagnostic_info
