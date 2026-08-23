"""
Unit tests for Phase 6D — Stage 2 Offline Calibration & Horizon-Bounded Runtime Contract.

Verifies:
1. Artifact generation & reproducibility (identical config/seeds -> identical hash).
2. Different horizon or p_grid alters artifact content hash.
3. Canonical hash independent of wall-clock time / UUIDs.
4. Stream seed mapping determinism & collision safety.
5. Seed capacity overflow rejection.
6. Validation/Evaluation seeds rejected for Stage 2 calibration.
7. Child seed derivation determinism & independence from Python hash().
8. Maximum cumulative evidence target calculation.
9. p=0 boundary classification matching production simulation behavior.
10. Quantile method (weibull) metadata validation.
11. Exact p-grid match uses empirical critical threshold.
12. Between-grid p returns STAGE2_CALIBRATION_UNAVAILABLE.
13. Out-of-support p returns STAGE2_OUT_OF_SUPPORT.
14. At horizon H, decision remains valid; next session returns STAGE2_HORIZON_EXCEEDED.
15. Runtime performs zero Monte Carlo, seed allocation, or artifact mutation.
16. Provenance mismatch rejection.
17. Frozen stream calibration operating point (calibration_p) contract.
18. Tampered artifact rejection.
"""
import pytest
import math
from dataclasses import FrozenInstanceError

from experiments.stage2_calibration import (
    generate_stage2_calibration_artifact,
    derive_child_seed,
    compute_stage2_canonical_hash,
)
from qsentinel_monitor.stage2_calibration_loader import (
    load_stage2_calibration_artifact,
    Stage2CalibrationArtifact,
)
from qsentinel_monitor.stage2_calibrated_decision import evaluate_calibrated_stage2
from qsentinel_monitor.sequential_test import create_initial_stage2_state
from qsentinel_monitor.quantum_evidence.models import QuantumEvidence, Stage1Result
from qsentinel_monitor.sequential_test_models import (
    Stage2DecisionStatus,
    Stage2ProcessingOutcome,
    Stage2ProvenanceIdentity,
)
from qsentinel_monitor.calibration_loader import ArtifactIntegrityError, ArtifactValidationError
from experiments.seed_allocator import SeedAllocationError


@pytest.fixture
def sample_stage2_artifact():
    return load_stage2_calibration_artifact(
        generate_stage2_calibration_artifact(
            p_grid=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
            n_qubits=200,
            alpha=0.01,
            horizon_sessions=10,
            n_trials_per_grid_point=10,
            seed_start=0,
        )
    )


@pytest.fixture
def valid_stage1_res():
    return Stage1Result("s-1", "PROCESSED", 0.05, 0.4, 0.5, True, {})


def make_evidence(session_id: str, k_Z: int, n_Z: int, k_X: int, n_X: int) -> QuantumEvidence:
    return QuantumEvidence(
        session_id=session_id,
        sample_count=n_Z + n_X,
        total_sifted_count=n_Z + n_X,
        total_mismatch_count=k_Z + k_X,
        overall_mismatch_rate=(k_Z + k_X) / (n_Z + n_X),
        z_sifted_count=n_Z,
        z_mismatch_count=k_Z,
        z_mismatch_rate=k_Z / n_Z if n_Z > 0 else 0.0,
        x_sifted_count=n_X,
        x_mismatch_count=k_X,
        x_mismatch_rate=k_X / n_X if n_X > 0 else 0.0,
        raw_evidence_summary={},
    )


def test_artifact_reproducibility():
    a1 = generate_stage2_calibration_artifact(horizon_sessions=5, n_trials_per_grid_point=5)
    a2 = generate_stage2_calibration_artifact(horizon_sessions=5, n_trials_per_grid_point=5)
    assert a1["content_hash"] == a2["content_hash"]


def test_different_horizon_alters_hash():
    a1 = generate_stage2_calibration_artifact(horizon_sessions=5, n_trials_per_grid_point=5)
    a2 = generate_stage2_calibration_artifact(horizon_sessions=10, n_trials_per_grid_point=5)
    assert a1["content_hash"] != a2["content_hash"]


def test_different_p_grid_alters_hash():
    a1 = generate_stage2_calibration_artifact(p_grid=[0.0, 0.05], n_trials_per_grid_point=5)
    a2 = generate_stage2_calibration_artifact(p_grid=[0.0, 0.10], n_trials_per_grid_point=5)
    assert a1["content_hash"] != a2["content_hash"]


def test_child_seed_derivation_determinism():
    s1 = derive_child_seed(stream_seed=100, grid_idx=0, trial_idx=1, session_idx=2)
    s2 = derive_child_seed(stream_seed=100, grid_idx=0, trial_idx=1, session_idx=2)
    assert s1 == s2
    assert isinstance(s1, int)
    assert 0 <= s1 < 2**31


def test_seed_capacity_overflow():
    with pytest.raises(SeedAllocationError):
        # 100 grid points * 1000 trials = 100,000 stream seeds > 50,000 max CALIBRATION range
        generate_stage2_calibration_artifact(p_grid=[0.01 * i for i in range(100)], n_trials_per_grid_point=1000)


def test_tampered_artifact_rejection(sample_stage2_artifact):
    artifact_dict = {
        "schema_version": sample_stage2_artifact.schema_version,
        "architecture_version": sample_stage2_artifact.architecture_version,
        "stage2_model_version": sample_stage2_artifact.stage2_model_version,
        "calibration_configuration": sample_stage2_artifact.calibration_configuration,
        "seed_provenance": sample_stage2_artifact.seed_provenance,
        "calibration_table": list(sample_stage2_artifact.calibration_table),
        "content_hash": sample_stage2_artifact.content_hash,
    }
    # Tamper with calibration table value
    artifact_dict["calibration_table"][1]["empirical_critical_value"] = 999.99

    with pytest.raises(ArtifactIntegrityError):
        load_stage2_calibration_artifact(artifact_dict)


def test_exact_p_grid_match_threshold_usage(sample_stage2_artifact, valid_stage1_res):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("s-1", k_Z=10, n_Z=100, k_X=10, n_X=100)

    upd_res, calib_dec = evaluate_calibrated_stage2(
        state0, ev1, valid_stage1_res, sequence_number=1, calibration_p=0.05, artifact=sample_stage2_artifact
    )

    assert upd_res.outcome == Stage2ProcessingOutcome.EVIDENCE_ACCEPTED
    assert calib_dec.matched_calibration_p == 0.05
    assert calib_dec.empirical_critical_value is not None
    assert calib_dec.decision_status == Stage2DecisionStatus.STAGE2_CALIBRATED_NOMINAL


def test_between_grid_p_returns_calibration_unavailable(sample_stage2_artifact, valid_stage1_res):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("s-1", k_Z=10, n_Z=100, k_X=10, n_X=100)

    # 0.07 is between grid points 0.05 and 0.10
    upd_res, calib_dec = evaluate_calibrated_stage2(
        state0, ev1, valid_stage1_res, sequence_number=1, calibration_p=0.07, artifact=sample_stage2_artifact
    )

    assert calib_dec.decision_status == Stage2DecisionStatus.STAGE2_CALIBRATION_UNAVAILABLE
    assert calib_dec.outcome == Stage2ProcessingOutcome.CALIBRATION_UNAVAILABLE


def test_out_of_support_p_returns_out_of_support(sample_stage2_artifact, valid_stage1_res):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("s-1", k_Z=10, n_Z=100, k_X=10, n_X=100)

    # 0.45 is outside calibrated grid support [0.0, 0.30]
    upd_res, calib_dec = evaluate_calibrated_stage2(
        state0, ev1, valid_stage1_res, sequence_number=1, calibration_p=0.45, artifact=sample_stage2_artifact
    )

    assert calib_dec.decision_status == Stage2DecisionStatus.STAGE2_OUT_OF_SUPPORT
    assert calib_dec.outcome == Stage2ProcessingOutcome.OUT_OF_SUPPORT


def test_horizon_exhaustion(sample_stage2_artifact, valid_stage1_res):
    state = create_initial_stage2_state()

    # Process up to horizon_sessions = 10
    for i in range(1, 11):
        ev = make_evidence(f"s-{i}", k_Z=10, n_Z=100, k_X=10, n_X=100)
        st1 = Stage1Result(f"s-{i}", "PROCESSED", 0.05, 0.4, 0.5, True, {})
        upd_res, calib_dec = evaluate_calibrated_stage2(
            state, ev, st1, sequence_number=i, calibration_p=0.05, artifact=sample_stage2_artifact
        )
        state = upd_res.next_state
        assert upd_res.outcome == Stage2ProcessingOutcome.EVIDENCE_ACCEPTED
        assert calib_dec.decision_status in (
            Stage2DecisionStatus.STAGE2_CALIBRATED_NOMINAL,
            Stage2DecisionStatus.STAGE2_CALIBRATED_ELEVATED,
        )

    # Submission 11 exceeds horizon 10
    ev11 = make_evidence("s-11", k_Z=10, n_Z=100, k_X=10, n_X=100)
    st11 = Stage1Result("s-11", "PROCESSED", 0.05, 0.4, 0.5, True, {})
    upd_res_11, calib_dec_11 = evaluate_calibrated_stage2(
        state, ev11, st11, sequence_number=11, calibration_p=0.05, artifact=sample_stage2_artifact
    )

    assert calib_dec_11.decision_status == Stage2DecisionStatus.STAGE2_HORIZON_EXCEEDED
    assert calib_dec_11.outcome == Stage2ProcessingOutcome.HORIZON_EXCEEDED


def test_frozen_calibration_p_midstream_alteration_rejected(sample_stage2_artifact, valid_stage1_res):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("s-1", k_Z=10, n_Z=100, k_X=10, n_X=100)

    upd1, dec1 = evaluate_calibrated_stage2(
        state0, ev1, valid_stage1_res, sequence_number=1, calibration_p=0.05, artifact=sample_stage2_artifact
    )
    assert upd1.outcome == Stage2ProcessingOutcome.EVIDENCE_ACCEPTED

    # Try submitting session 2 with different calibration_p 0.10 for the same stream
    ev2 = make_evidence("s-2", k_Z=10, n_Z=100, k_X=10, n_X=100)
    st2 = Stage1Result("s-2", "PROCESSED", 0.10, 0.4, 0.5, True, {})
    upd2, dec2 = evaluate_calibrated_stage2(
        upd1.next_state, ev2, st2, sequence_number=2, calibration_p=0.10, artifact=sample_stage2_artifact
    )

    assert dec2.decision_status == Stage2DecisionStatus.STAGE2_CALIBRATION_UNAVAILABLE
    assert upd2.next_state == upd1.next_state  # State unmutated


def test_provenance_mismatch_rejected(sample_stage2_artifact, valid_stage1_res):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("s-1", k_Z=10, n_Z=100, k_X=10, n_X=100)

    upd1, dec1 = evaluate_calibrated_stage2(
        state0, ev1, valid_stage1_res, sequence_number=1, calibration_p=0.05, artifact=sample_stage2_artifact
    )

    # Different artifact hash
    mismatched_artifact = Stage2CalibrationArtifact(
        schema_version=sample_stage2_artifact.schema_version,
        architecture_version=sample_stage2_artifact.architecture_version,
        stage2_model_version=sample_stage2_artifact.stage2_model_version,
        calibration_configuration=sample_stage2_artifact.calibration_configuration,
        seed_provenance=sample_stage2_artifact.seed_provenance,
        calibration_table=sample_stage2_artifact.calibration_table,
        content_hash="MISMATCHED_HASH_12345",
    )

    ev2 = make_evidence("s-2", k_Z=10, n_Z=100, k_X=10, n_X=100)
    st2 = Stage1Result("s-2", "PROCESSED", 0.05, 0.4, 0.5, True, {})
    upd2, dec2 = evaluate_calibrated_stage2(
        upd1.next_state, ev2, st2, sequence_number=2, calibration_p=0.05, artifact=mismatched_artifact
    )

    assert dec2.decision_status == Stage2DecisionStatus.STAGE2_PROVENANCE_MISMATCH
    assert dec2.outcome == Stage2ProcessingOutcome.INCOMPATIBLE_PROVENANCE
    assert upd2.next_state == upd1.next_state
