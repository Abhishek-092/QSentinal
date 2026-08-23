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
    assert res.status == "MODEL_VALID"
    assert res.model_valid is True
    assert res.best_fit_p == 0.0
    assert res.statistic == 0.0
    assert res.optimization_success is True


def test_stage1_honest_noise_recovery():
    """Verify Stage 1 accurately recovers best-fit noise parameter p for p=0.04."""
    config = SessionConfig(n_qubits=500, noise_parameter_p=0.04, seed=777)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    res = evaluate_stage1(evidence)

    assert res.status == "MODEL_VALID"
    assert res.optimization_success is True
    assert pytest.approx(res.best_fit_p, abs=0.02) == 0.04
    assert res.statistic < 15.0


def test_stage1_inconsistent_synthetic_evidence():
    """Verify Stage 1 flags synthetic evidence where m, C, H violate single depolarizing p relationship."""
    # Synthetic evidence with incompatible m=0.02, C=-0.80 (which implies m=0.9), H=0.95
    inconsistent_evidence = QuantumEvidence(
        session_id="synth_inconsistent",
        sample_count=200,
        sifted_count=100,
        mismatch_count=2,
        mismatch_rate=0.02,
        correlation=-0.80,  # Highly inconsistent with m=0.02 (expected C=0.96)
        entropy=0.95,        # Inconsistent with m=0.02 (expected H=0.14)
        pauli_correction_consistency=1.0,
        raw_evidence_summary={}
    )
    res = evaluate_stage1(inconsistent_evidence)

    assert res.status == "MODEL_INVALID"
    assert res.model_valid is False
    assert res.statistic > 15.0


def test_stage1_joint_parameterization_not_independent_multiplication():
    """
    Explicit test asserting that Stage 1 uses a joint model parameterization
    and does NOT multiply independent marginal probabilities P(m)*P(C)*P(H).
    """
    # Evaluate Stage 1 on a low-noise session
    config = SessionConfig(n_qubits=200, noise_parameter_p=0.03, seed=12)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    res = evaluate_stage1(evidence)

    # Diagnostic info should report joint profile likelihood stats
    assert "best_fit_p" in res.diagnostic_info
    assert "sat_loss" in res.diagnostic_info
    assert "min_loss" in res.diagnostic_info
    # Joint loss difference T = 2*(min_loss - sat_loss)
    expected_T = 2.0 * (res.diagnostic_info["min_loss"] - res.diagnostic_info["sat_loss"])
    assert pytest.approx(res.statistic, abs=1e-5) == max(expected_T, 0.0)
