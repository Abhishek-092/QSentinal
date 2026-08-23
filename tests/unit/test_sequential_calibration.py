import pytest
import json
import numpy as np
from qds.protocol import SessionConfig, run_session
from experiments.calibration import generate_calibration_artifact
from qsentinel_monitor.calibration_loader import load_calibration_artifact
from experiments.sequential_calibration import generate_sequential_calibration_artifact
from qsentinel_monitor.sequential_calibration_loader import (
    load_sequential_calibration_artifact,
    SequentialArtifactIntegrityError,
    SequentialArtifactValidationError,
)
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from qsentinel_monitor.calibrated_decision import evaluate_calibrated_stage1
from qsentinel_monitor.sequential_evidence import create_initial_sequential_state, update_sequential_evidence
from qsentinel_monitor.sequential_evidence_models import SessionProcessingOutcome, SequentialDecisionStatus
from experiments.seed_allocator import SeedAllocator, SeedAllocationError


@pytest.fixture
def st1_artifact():
    art_dict = generate_calibration_artifact(
        p_grid=[0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3],
        n_qubits=200,
        alpha=0.01,
        n_trials_per_grid_point=20,
    )
    return load_calibration_artifact(art_dict)


@pytest.fixture
def seq_artifact(st1_artifact):
    seq_art_dict = generate_sequential_calibration_artifact(
        stage1_artifact=st1_artifact,
        monitoring_horizon_sessions=10,
        alpha_seq=0.01,
        n_trials=20,
        seed_start=10000,
        tolerance=0.05,
    )
    return load_sequential_calibration_artifact(seq_art_dict)


# 1. REPRODUCIBILITY & HASHING
def test_sequential_artifact_reproducibility(st1_artifact):
    a1 = generate_sequential_calibration_artifact(st1_artifact, monitoring_horizon_sessions=5, n_trials=10, tolerance=0.05)
    a2 = generate_sequential_calibration_artifact(st1_artifact, monitoring_horizon_sessions=5, n_trials=10, tolerance=0.05)

    assert a1["content_hash"] == a2["content_hash"]
    assert a1 == a2


# 2. PROVENANCE BINDING
def test_sequential_artifact_stage1_provenance_binding(st1_artifact, seq_artifact):
    st1_hash = st1_artifact.content_hash
    assert seq_artifact.stage1_calibration_provenance["artifact_content_hash"] == st1_hash


# 3. DIFFERENT HORIZON ALTERS PROVENANCE/HASH
def test_different_horizon_alters_hash(st1_artifact):
    a1 = generate_sequential_calibration_artifact(st1_artifact, monitoring_horizon_sessions=5, n_trials=10, tolerance=0.05)
    a2 = generate_sequential_calibration_artifact(st1_artifact, monitoring_horizon_sessions=10, n_trials=10, tolerance=0.05)

    assert a1["content_hash"] != a2["content_hash"]


# 4. DIFFERENT ALPHA_SEQ ALTERS PROVENANCE/HASH
def test_different_alpha_seq_alters_hash(st1_artifact):
    a1 = generate_sequential_calibration_artifact(st1_artifact, alpha_seq=0.01, n_trials=10, tolerance=0.05)
    a2 = generate_sequential_calibration_artifact(st1_artifact, alpha_seq=0.05, n_trials=10, tolerance=0.05)

    assert a1["content_hash"] != a2["content_hash"]


# 5. SEED CAPACITY OVERFLOW REJECTION
def test_seed_capacity_overflow_rejection(st1_artifact):
    with pytest.raises(SeedAllocationError):
        # 1000 trials * 100 sessions = 100,000 seeds > 50,000 limit
        generate_sequential_calibration_artifact(st1_artifact, monitoring_horizon_sessions=100, n_trials=1000, tolerance=0.05)


# 6. SEED SEPARATION GUARANTEE
def test_seed_range_validation():
    # Valid calibration seed
    assert SeedAllocator.validate_seed("CALIBRATION", 100) is True

    # Seed 50,000 is outside CALIBRATION range [0, 50_000)
    with pytest.raises(SeedAllocationError):
        SeedAllocator.validate_seed("CALIBRATION", 50_000)

    # Seed 100 is outside VALIDATION range [50_000, 100_000)
    with pytest.raises(SeedAllocationError):
        SeedAllocator.validate_seed("VALIDATION", 100)


# 7. MAX STATISTIC DEFINITION IN ARTIFACT
def test_max_statistic_definition(seq_artifact):
    assert seq_artifact.calibration_summary["max_statistic_definition"] == "max(E_1, ..., E_K)"
    assert seq_artifact.empirical_sequential_threshold >= 0.0


# 8. TAMPERING DETECTION
def test_sequential_artifact_tampering_detection(seq_artifact):
    dict_repr = json.loads(json.dumps(seq_artifact.__dict__))
    dict_repr["empirical_sequential_threshold"] += 999.0

    with pytest.raises(SequentialArtifactIntegrityError):
        load_sequential_calibration_artifact(dict_repr)


# 9. RUNTIME USES ARTIFACT THRESHOLD
def test_runtime_uses_sequential_artifact_threshold(st1_artifact, seq_artifact):
    config = SessionConfig(n_qubits=200, noise_parameter_p=0.10, seed=1)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    stage1_res = evaluate_stage1(evidence)
    calib_dec = evaluate_calibrated_stage1(stage1_res, st1_artifact, tolerance=0.05)

    s0 = create_initial_sequential_state()
    res = update_sequential_evidence(s0, calib_dec, sequential_artifact=seq_artifact)

    assert res.outcome == SessionProcessingOutcome.EVIDENCE_ACCEPTED
    assert f"{seq_artifact.empirical_sequential_threshold:.4f}" in res.diagnostic_reason


# 10. STAGE 1 PROVENANCE MISMATCH REJECTION
def test_stage1_provenance_mismatch_rejection(st1_artifact, seq_artifact):
    config = SessionConfig(n_qubits=200, noise_parameter_p=0.10, seed=1)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)
    stage1_res = evaluate_stage1(evidence)
    calib_dec = evaluate_calibrated_stage1(stage1_res, st1_artifact, tolerance=0.05)

    # Modify decision's artifact_content_hash
    calib_dec_mismatched = evaluate_calibrated_stage1(stage1_res, st1_artifact, tolerance=0.05)
    object.__setattr__(calib_dec_mismatched, "artifact_content_hash", "mismatched_hash_123")

    s0 = create_initial_sequential_state()
    res = update_sequential_evidence(s0, calib_dec_mismatched, sequential_artifact=seq_artifact)

    assert res.outcome == SessionProcessingOutcome.INCOMPATIBLE_PROVENANCE
    assert res.next_state == s0


# 11. HORIZON EXHAUSTION HANDLING
def test_horizon_exhaustion_handling(st1_artifact, seq_artifact):
    # seq_artifact horizon is K=10 sessions
    s_curr = create_initial_sequential_state()

    # Feed sessions until K=10 processed_valid_count is reached
    seed = 100
    valid_fed = 0
    while valid_fed < 10:
        config = SessionConfig(n_qubits=200, noise_parameter_p=0.10, seed=seed)
        seed += 1
        transcript = run_session(config)
        evidence = extract_evidence(transcript)
        stage1_res = evaluate_stage1(evidence)
        calib_dec = evaluate_calibrated_stage1(stage1_res, st1_artifact, tolerance=0.05)
        r = update_sequential_evidence(s_curr, calib_dec, sequential_artifact=seq_artifact)
        s_curr = r.next_state
        if r.outcome == SessionProcessingOutcome.EVIDENCE_ACCEPTED:
            valid_fed += 1

    assert s_curr.processed_valid_count == 10

    # Next valid session exceeds horizon K=10
    config_11 = SessionConfig(n_qubits=200, noise_parameter_p=0.10, seed=999)
    transcript_11 = run_session(config_11)
    evidence_11 = extract_evidence(transcript_11)
    stage1_res_11 = evaluate_stage1(evidence_11)
    calib_dec_11 = evaluate_calibrated_stage1(stage1_res_11, st1_artifact, tolerance=0.05)

    res_exceeded = update_sequential_evidence(s_curr, calib_dec_11, sequential_artifact=seq_artifact)
    assert res_exceeded.outcome == SessionProcessingOutcome.HORIZON_EXCEEDED
    assert res_exceeded.next_state.decision_status == SequentialDecisionStatus.SEQUENTIAL_HORIZON_EXCEEDED
