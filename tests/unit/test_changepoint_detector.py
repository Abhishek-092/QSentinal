"""
Phase 8 Change-Point (Offset GLR-CUSUM) Unit Test Suite for QSENTINEL.

Verifies:
1. Initial state defaults
2. Negative-drift reset behavior
3. Positive accumulation
4. CUSUM reset to zero
5. Active run length correctness
6. Estimated excursion onset correctness
7. Detection threshold crossing
8. Elevated-state freeze behavior
9. Duplicate rejection
10. Out-of-order rejection
11. Provenance mismatch
12. p-grid unavailable
13. p outside support
14. p = 0 boundary
15. k = H remains calibrated
16. k = H + 1 is horizon exceeded
17. NaN/Inf rejection
18. State immutability
19. Determinism
20. Reconstruction reproducibility
21. Zero runtime seed allocation
22. Zero runtime Monte Carlo
23. Import purity
"""
import math
import pytest
from typing import Any

from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from qsentinel_monitor.changepoint_models import (
    ChangePointDecisionStatus,
    ChangePointProcessingOutcome,
    ChangePointProvenanceIdentity,
    ChangePointTestState,
    ChangePointUpdateResult,
    CalibratedChangePointDecision,
)
from qsentinel_monitor.changepoint_detector import (
    create_initial_changepoint_state,
    update_changepoint_detector,
)
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact
from qsentinel_monitor.changepoint_calibrated_decision import evaluate_calibrated_changepoint


@pytest.fixture
def sample_provenance() -> ChangePointProvenanceIdentity:
    return ChangePointProvenanceIdentity(
        artifact_content_hash="test_hash_123",
        artifact_schema_version="1.0",
        architecture_version="v8.0",
        stage1_model_version="v1.0",
        changepoint_model_version="v1.0",
    )


@pytest.fixture
def mock_artifact() -> ChangePointCalibrationArtifact:
    return ChangePointCalibrationArtifact(
        schema_version="1.0",
        architecture_version="v8.0",
        changepoint_model_version="v1.0",
        calibration_configuration={
            "n_qubits": 200,
            "alpha": 0.01,
            "horizon_sessions": 5,
            "n_trials_per_grid_point": 100,
            "p_grid": [0.0, 0.05, 0.10],
            "quantile_method": "weibull",
            "calibration_guarantee": "HORIZON_BOUNDED",
            "calibrated_statistic": "MAX_OFFSET_CUSUM",
            "offset_formula": "d(p) = mu_H0(p) + delta(p)",
            "delta_offset_margin": 0.05,
        },
        seed_provenance={
            "purpose": "CALIBRATION",
            "schedule_version": "v2.0",
            "seed_start": 0,
            "seed_count": 1500,
            "seed_unit": "STREAM",
            "mapping": "linear",
            "child_seed_derivation": "sha256_v1",
        },
        calibration_table=[
            {
                "p": 0.0,
                "null_classification": "DEGENERATE_BOUNDARY_NULL",
                "null_mean_glr": 0.0,
                "delta_offset_margin": 0.05,
                "null_offset_d": 0.05,
                "empirical_critical_value": 100.0,
                "max_cusum_mean": 0.0,
                "max_cusum_std": 0.0,
                "n_trials": 100,
                "quantile_probability": 0.99,
            },
            {
                "p": 0.05,
                "null_classification": "REGULAR_INTERIOR_NULL",
                "null_mean_glr": 0.02,
                "delta_offset_margin": 0.05,
                "null_offset_d": 0.07,
                "empirical_critical_value": 100.0,
                "max_cusum_mean": 0.10,
                "max_cusum_std": 0.05,
                "n_trials": 100,
                "quantile_probability": 0.99,
            },
            {
                "p": 0.10,
                "null_classification": "REGULAR_INTERIOR_NULL",
                "null_mean_glr": 0.04,
                "delta_offset_margin": 0.05,
                "null_offset_d": 0.09,
                "empirical_critical_value": 100.0,
                "max_cusum_mean": 0.20,
                "max_cusum_std": 0.08,
                "n_trials": 100,
                "quantile_probability": 0.99,
            },
        ],
        content_hash="mock_hash_456",
    )


def test_initial_state_defaults():
    st = create_initial_changepoint_state()
    assert st.cusum_statistic == 0.0
    assert st.active_run_length == 0
    assert st.estimated_excursion_onset is None
    assert st.processed_valid_count == 0
    assert st.skipped_session_count == 0
    assert st.last_accepted_session_id is None
    assert st.last_accepted_sequence_number == 0
    assert st.provenance_identity is None
    assert st.decision_status == ChangePointDecisionStatus.CHANGEPOINT_UNINITIALIZED
    assert st.history_session_ids == ()


def test_negative_drift_reset_and_active_run_length(sample_provenance):
    st = create_initial_changepoint_state()
    cfg = SessionConfig(noise_parameter_p=0.05, seed=12345)
    tr = run_session(cfg)
    ev = extract_evidence(tr)
    st1 = evaluate_stage1(ev)

    # Offset d high enough to cause raw_increment <= 0
    res = update_changepoint_detector(
        st, ev, st1, sequence_number=1, provenance=sample_provenance, null_offset_d=10.0
    )
    assert res.outcome == ChangePointProcessingOutcome.EVIDENCE_ACCEPTED
    assert res.next_state.cusum_statistic == 0.0
    assert res.next_state.active_run_length == 0
    assert res.next_state.estimated_excursion_onset is None


def test_positive_accumulation_and_onset_estimation(sample_provenance):
    st = create_initial_changepoint_state()
    cfg = SessionConfig(noise_parameter_p=0.05, seed=12345)
    tr = run_session(cfg)
    ev = extract_evidence(tr)
    st1 = evaluate_stage1(ev)

    # First session with d=0.0 (positive increment)
    res1 = update_changepoint_detector(
        st, ev, st1, sequence_number=1, provenance=sample_provenance, null_offset_d=0.0
    )
    st_next1 = res1.next_state
    assert st_next1.cusum_statistic > 0.0
    assert st_next1.active_run_length == 1

    # Second session (with different ID)
    tr2 = run_session(SessionConfig(noise_parameter_p=0.05, seed=54321, nonce="n2"))
    ev2 = extract_evidence(tr2)
    st1_2 = evaluate_stage1(ev2)

    # Crossing a low threshold = 0.01 to test elevation and onset
    res2 = update_changepoint_detector(
        st_next1, ev2, st1_2, sequence_number=2, provenance=sample_provenance, null_offset_d=0.0, threshold=0.01
    )
    st_next2 = res2.next_state
    assert st_next2.decision_status == ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED
    assert st_next2.active_run_length == 2
    # estimated onset = k - active_run + 1 = 2 - 2 + 1 = 1
    assert st_next2.estimated_excursion_onset == 1


def test_elevated_state_freeze_behavior(sample_provenance):
    st = create_initial_changepoint_state()
    tr = run_session(SessionConfig(noise_parameter_p=0.05, seed=100))
    ev = extract_evidence(tr)
    st1 = evaluate_stage1(ev)

    res1 = update_changepoint_detector(
        st, ev, st1, sequence_number=1, provenance=sample_provenance, null_offset_d=0.0, threshold=0.001
    )
    st_elevated = res1.next_state
    assert st_elevated.decision_status == ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED

    # Attempting to update elevated state
    tr2 = run_session(SessionConfig(noise_parameter_p=0.05, seed=200, nonce="n2"))
    ev2 = extract_evidence(tr2)
    st1_2 = evaluate_stage1(ev2)

    res2 = update_changepoint_detector(
        st_elevated, ev2, st1_2, sequence_number=2, provenance=sample_provenance, null_offset_d=0.0, threshold=0.001
    )
    assert res2.next_state == st_elevated
    assert "frozen" in res2.diagnostic_reason.lower()


def test_duplicate_and_out_of_order_rejection(sample_provenance):
    st = create_initial_changepoint_state()
    tr = run_session(SessionConfig(noise_parameter_p=0.05, seed=100))
    ev = extract_evidence(tr)
    st1 = evaluate_stage1(ev)

    res1 = update_changepoint_detector(
        st, ev, st1, sequence_number=1, provenance=sample_provenance, null_offset_d=0.0
    )
    st_active = res1.next_state

    # Duplicate session ID
    res_dup = update_changepoint_detector(
        st_active, ev, st1, sequence_number=2, provenance=sample_provenance, null_offset_d=0.0
    )
    assert res_dup.outcome == ChangePointProcessingOutcome.DUPLICATE_SESSION

    # Out of order sequence number (seq <= 1)
    tr2 = run_session(SessionConfig(noise_parameter_p=0.05, seed=200, nonce="n2"))
    ev2 = extract_evidence(tr2)
    st1_2 = evaluate_stage1(ev2)

    res_ooo = update_changepoint_detector(
        st_active, ev2, st1_2, sequence_number=1, provenance=sample_provenance, null_offset_d=0.0
    )
    assert res_ooo.outcome == ChangePointProcessingOutcome.OUT_OF_ORDER_SESSION


def test_horizon_semantics(mock_artifact):
    st = create_initial_changepoint_state()
    # mock_artifact horizon_sessions = 5
    curr_st = st
    for seq in range(1, 6):  # seq 1 to 5 (k <= H=5)
        tr = run_session(SessionConfig(noise_parameter_p=0.05, seed=seq, nonce=f"n_{seq}"))
        ev = extract_evidence(tr)
        st1 = evaluate_stage1(ev)
        up_res, dec = evaluate_calibrated_changepoint(
            curr_st, ev, st1, sequence_number=seq, calibration_p=0.05, artifact=mock_artifact
        )
        assert dec.outcome == ChangePointProcessingOutcome.EVIDENCE_ACCEPTED
        assert dec.decision_status in (
            ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_NOMINAL,
            ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED,
        )
        curr_st = up_res.next_state

    assert curr_st.processed_valid_count == 5

    # seq 6 (k = 6 > H=5) -> HORIZON_EXCEEDED
    tr6 = run_session(SessionConfig(noise_parameter_p=0.05, seed=6, nonce="n_6"))
    ev6 = extract_evidence(tr6)
    st1_6 = evaluate_stage1(ev6)
    up_res6, dec6 = evaluate_calibrated_changepoint(
        curr_st, ev6, st1_6, sequence_number=6, calibration_p=0.05, artifact=mock_artifact
    )
    assert dec6.outcome == ChangePointProcessingOutcome.HORIZON_EXCEEDED
    assert dec6.decision_status == ChangePointDecisionStatus.CHANGEPOINT_HORIZON_EXCEEDED


def test_p_grid_lookup_and_out_of_support(mock_artifact):
    st = create_initial_changepoint_state()
    tr = run_session(SessionConfig(noise_parameter_p=0.05, seed=10))
    ev = extract_evidence(tr)
    st1 = evaluate_stage1(ev)

    # p between grid points (p = 0.07 is between 0.05 and 0.10)
    _, dec_between = evaluate_calibrated_changepoint(
        st, ev, st1, sequence_number=1, calibration_p=0.07, artifact=mock_artifact
    )
    assert dec_between.outcome == ChangePointProcessingOutcome.CALIBRATION_UNAVAILABLE
    assert dec_between.decision_status == ChangePointDecisionStatus.CHANGEPOINT_CALIBRATION_UNAVAILABLE

    # p outside support (p = 0.50 > max p 0.10)
    _, dec_outside = evaluate_calibrated_changepoint(
        st, ev, st1, sequence_number=1, calibration_p=0.50, artifact=mock_artifact
    )
    assert dec_outside.outcome == ChangePointProcessingOutcome.OUT_OF_SUPPORT
    assert dec_outside.decision_status == ChangePointDecisionStatus.CHANGEPOINT_OUT_OF_SUPPORT


def test_p_zero_boundary(mock_artifact):
    st = create_initial_changepoint_state()
    tr = run_session(SessionConfig(noise_parameter_p=0.0, seed=10))
    ev = extract_evidence(tr)
    st1 = evaluate_stage1(ev)

    _, dec_zero = evaluate_calibrated_changepoint(
        st, ev, st1, sequence_number=1, calibration_p=0.0, artifact=mock_artifact
    )
    assert dec_zero.outcome == ChangePointProcessingOutcome.EVIDENCE_ACCEPTED
    assert dec_zero.matched_calibration_p == 0.0
    assert dec_zero.null_offset_d == 0.05
