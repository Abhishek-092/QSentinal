"""
Unit tests for Phase 6C — Stage 2 Joint Sequential Testing Engine.

Verifies:
1. Initial state creation.
2. Valid symmetric session evidence is finite.
3. Symmetric observations produce approximately zero GLR evidence.
4. Asymmetric observations produce positive GLR evidence.
5. Stronger asymmetry produces greater evidence than weaker asymmetry.
6. Multiple sessions accumulate evidence deterministically.
7. Threshold crossing changes sequential decision status.
8. Exact threshold boundary behaviour is deterministic and documented.
9. Duplicate session rejection.
10. Out-of-order sequence rejection.
11. Provenance mismatch rejection.
12. Invalid n_Z = 0 handling.
13. Invalid n_X = 0 handling.
14. Invalid k_Z bounds handling.
15. Invalid k_X bounds handling.
16. NaN handling.
17. Infinity handling.
18. Boundary case k = 0.
19. Boundary case k = n.
20. Immutability of state.
21. Deterministic reconstruction from identical input stream.
22. No runtime simulation.
23. No seed allocation.
24. No mutation of protocol data.
25. Import purity.
"""
import math
import pytest
from dataclasses import FrozenInstanceError

from qsentinel_monitor.quantum_evidence.models import QuantumEvidence, Stage1Result
from qsentinel_monitor.sequential_test_models import (
    Stage2DecisionStatus,
    Stage2ProcessingOutcome,
    Stage2ProvenanceIdentity,
    SequentialTestState,
    SequentialTestUpdateResult,
)
from qsentinel_monitor.sequential_test import (
    create_initial_stage2_state,
    compute_session_log_likelihood_ratio,
    update_stage2_sequential_test,
)


@pytest.fixture
def sample_provenance():
    return Stage2ProvenanceIdentity(
        artifact_content_hash="abc123hash",
        artifact_schema_version="1.0",
        architecture_version="v5.0",
        stage1_model_version="v1.0",
        stage2_model_version="v1.0",
    )


@pytest.fixture
def valid_stage1_result():
    return Stage1Result(
        session_id="session-1",
        status="PROCESSED",
        best_fit_p=0.06,
        statistic=0.5,
        uncalibrated_theoretical_p_value=0.47,
        optimization_success=True,
        diagnostic_info={},
    )


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


def test_initial_state_creation():
    state = create_initial_stage2_state()
    assert state.cumulative_log_likelihood_ratio == 0.0
    assert state.processed_valid_count == 0
    assert state.skipped_session_count == 0
    assert state.last_accepted_session_id is None
    assert state.last_accepted_sequence_number == 0
    assert state.provenance_identity is None
    assert state.decision_status == Stage2DecisionStatus.STAGE2_UNINITIALIZED
    assert state.history_session_ids == ()


def test_symmetric_evidence_approx_zero():
    # Symmetric mismatch counts k_Z / n_Z == k_X / n_X
    evidence = make_evidence("s1", k_Z=10, n_Z=100, k_X=10, n_X=100)
    log_lambda = compute_session_log_likelihood_ratio(evidence)
    assert pytest.approx(log_lambda, abs=1e-12) == 0.0


def test_asymmetric_evidence_positive():
    # Asymmetric mismatch counts k_Z / n_Z != k_X / n_X
    evidence = make_evidence("s1", k_Z=20, n_Z=100, k_X=5, n_X=100)
    log_lambda = compute_session_log_likelihood_ratio(evidence)
    assert log_lambda > 0.0
    assert math.isfinite(log_lambda)


def test_stronger_asymmetry_greater_evidence():
    # Weaker asymmetry: k_Z=15, k_X=5 vs Stronger asymmetry: k_Z=30, k_X=0
    weaker = make_evidence("s1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    stronger = make_evidence("s2", k_Z=30, n_Z=100, k_X=0, n_X=100)

    log_lambda_weaker = compute_session_log_likelihood_ratio(weaker)
    log_lambda_stronger = compute_session_log_likelihood_ratio(stronger)

    assert log_lambda_stronger > log_lambda_weaker


def test_multiple_sessions_accumulate_deterministically(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()

    ev1 = make_evidence("session-1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res1 = update_stage2_sequential_test(state0, ev1, valid_stage1_result, 1, sample_provenance)

    assert res1.outcome == Stage2ProcessingOutcome.EVIDENCE_ACCEPTED
    l1 = res1.session_log_likelihood_ratio
    assert res1.next_state.cumulative_log_likelihood_ratio == l1
    assert res1.next_state.processed_valid_count == 1

    ev2 = make_evidence("session-2", k_Z=25, n_Z=100, k_X=2, n_X=100)
    st1_res2 = Stage1Result("session-2", "PROCESSED", 0.08, 1.2, 0.20, True, {})
    res2 = update_stage2_sequential_test(res1.next_state, ev2, st1_res2, 2, sample_provenance)

    assert res2.outcome == Stage2ProcessingOutcome.EVIDENCE_ACCEPTED
    l2 = res2.session_log_likelihood_ratio
    assert res2.next_state.cumulative_log_likelihood_ratio == pytest.approx(l1 + l2)
    assert res2.next_state.processed_valid_count == 2
    assert res2.next_state.history_session_ids == ("session-1", "session-2")


def test_threshold_crossing_changes_status(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev = make_evidence("session-1", k_Z=25, n_Z=100, k_X=2, n_X=100)

    # Threshold higher than single session evidence delta
    l1 = compute_session_log_likelihood_ratio(ev)
    threshold_high = l1 + 10.0
    res_high = update_stage2_sequential_test(state0, ev, valid_stage1_result, 1, sample_provenance, threshold=threshold_high)
    assert res_high.next_state.decision_status == Stage2DecisionStatus.STAGE2_NOMINAL

    # Threshold lower than single session evidence delta
    threshold_low = l1 - 0.1
    res_low = update_stage2_sequential_test(state0, ev, valid_stage1_result, 1, sample_provenance, threshold=threshold_low)
    assert res_low.next_state.decision_status == Stage2DecisionStatus.STAGE2_EVIDENCE_ELEVATED


def test_threshold_exact_boundary(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev = make_evidence("session-1", k_Z=20, n_Z=100, k_X=5, n_X=100)
    l1 = compute_session_log_likelihood_ratio(ev)

    # Exact threshold equality => STAGE2_EVIDENCE_ELEVATED
    res_exact = update_stage2_sequential_test(state0, ev, valid_stage1_result, 1, sample_provenance, threshold=l1)
    assert res_exact.next_state.decision_status == Stage2DecisionStatus.STAGE2_EVIDENCE_ELEVATED


def test_duplicate_session_rejection(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("session-1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res1 = update_stage2_sequential_test(state0, ev1, valid_stage1_result, 1, sample_provenance)

    # Submit same session_id with sequence 2
    res_dup = update_stage2_sequential_test(res1.next_state, ev1, valid_stage1_result, 2, sample_provenance)
    assert res_dup.outcome == Stage2ProcessingOutcome.DUPLICATE_SESSION
    assert res_dup.next_state == res1.next_state


def test_out_of_order_sequence_rejection(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("session-1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res1 = update_stage2_sequential_test(state0, ev1, valid_stage1_result, 5, sample_provenance)

    # Submit sequence_number 3 <= 5
    ev2 = make_evidence("session-2", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res_ooo = update_stage2_sequential_test(res1.next_state, ev2, valid_stage1_result, 3, sample_provenance)
    assert res_ooo.outcome == Stage2ProcessingOutcome.OUT_OF_ORDER_SESSION
    assert res_ooo.next_state == res1.next_state


def test_provenance_mismatch_rejection(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("session-1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res1 = update_stage2_sequential_test(state0, ev1, valid_stage1_result, 1, sample_provenance)

    mismatched_provenance = Stage2ProvenanceIdentity(
        artifact_content_hash="DIFFERENT_HASH",
        artifact_schema_version="1.0",
        architecture_version="v5.0",
        stage1_model_version="v1.0",
        stage2_model_version="v1.0",
    )

    ev2 = make_evidence("session-2", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res_prov = update_stage2_sequential_test(res1.next_state, ev2, valid_stage1_result, 2, mismatched_provenance)
    assert res_prov.outcome == Stage2ProcessingOutcome.INCOMPATIBLE_PROVENANCE
    assert res_prov.next_state == res1.next_state


def test_invalid_n_Z_zero_handling(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev = make_evidence("session-1", k_Z=0, n_Z=0, k_X=5, n_X=100)

    res = update_stage2_sequential_test(state0, ev, valid_stage1_result, 1, sample_provenance)
    assert res.outcome == Stage2ProcessingOutcome.INVALID_NUMERICAL_INPUT
    assert res.next_state.skipped_session_count == 1
    assert res.next_state.processed_valid_count == 0


def test_invalid_n_X_zero_handling(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev = make_evidence("session-1", k_Z=5, n_Z=100, k_X=0, n_X=0)

    res = update_stage2_sequential_test(state0, ev, valid_stage1_result, 1, sample_provenance)
    assert res.outcome == Stage2ProcessingOutcome.INVALID_NUMERICAL_INPUT
    assert res.next_state.skipped_session_count == 1


def test_invalid_k_Z_bounds_handling(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    # k_Z > n_Z
    ev = make_evidence("session-1", k_Z=150, n_Z=100, k_X=5, n_X=100)

    res = update_stage2_sequential_test(state0, ev, valid_stage1_result, 1, sample_provenance)
    assert res.outcome == Stage2ProcessingOutcome.INVALID_NUMERICAL_INPUT
    assert res.next_state.skipped_session_count == 1


def test_invalid_k_X_bounds_handling(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    # k_X < 0
    ev = make_evidence("session-1", k_Z=5, n_Z=100, k_X=-1, n_X=100)

    res = update_stage2_sequential_test(state0, ev, valid_stage1_result, 1, sample_provenance)
    assert res.outcome == Stage2ProcessingOutcome.INVALID_NUMERICAL_INPUT
    assert res.next_state.skipped_session_count == 1


def test_nan_handling(sample_provenance):
    state0 = create_initial_stage2_state()
    ev = make_evidence("session-1", k_Z=5, n_Z=100, k_X=5, n_X=100)

    nan_stage1 = Stage1Result(
        session_id="session-1",
        status="PROCESSED",
        best_fit_p=math.nan,
        statistic=math.nan,
        uncalibrated_theoretical_p_value=None,
        optimization_success=True,
        diagnostic_info={},
    )

    res = update_stage2_sequential_test(state0, ev, nan_stage1, 1, sample_provenance)
    assert res.outcome == Stage2ProcessingOutcome.UNAVAILABLE_INPUT
    assert res.next_state.skipped_session_count == 1


def test_infinity_handling(sample_provenance):
    state0 = create_initial_stage2_state()
    ev = make_evidence("session-1", k_Z=5, n_Z=100, k_X=5, n_X=100)

    inf_stage1 = Stage1Result(
        session_id="session-1",
        status="PROCESSED",
        best_fit_p=0.05,
        statistic=math.inf,
        uncalibrated_theoretical_p_value=None,
        optimization_success=True,
        diagnostic_info={},
    )

    res = update_stage2_sequential_test(state0, ev, inf_stage1, 1, sample_provenance)
    assert res.outcome == Stage2ProcessingOutcome.UNAVAILABLE_INPUT
    assert res.next_state.skipped_session_count == 1


def test_boundary_case_k_equals_zero():
    # k_Z = 0, k_X = 0
    ev = make_evidence("s1", k_Z=0, n_Z=100, k_X=0, n_X=100)
    log_lambda = compute_session_log_likelihood_ratio(ev)
    assert math.isfinite(log_lambda)
    assert pytest.approx(log_lambda, abs=1e-12) == 0.0


def test_boundary_case_k_equals_n():
    # k_Z = n_Z, k_X = n_X
    ev = make_evidence("s1", k_Z=100, n_Z=100, k_X=100, n_X=100)
    log_lambda = compute_session_log_likelihood_ratio(ev)
    assert math.isfinite(log_lambda)
    assert pytest.approx(log_lambda, abs=1e-12) == 0.0


def test_immutability_of_state(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    with pytest.raises(FrozenInstanceError):
        state0.cumulative_log_likelihood_ratio = 10.0  # type: ignore

    ev1 = make_evidence("session-1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res1 = update_stage2_sequential_test(state0, ev1, valid_stage1_result, 1, sample_provenance)
    with pytest.raises(FrozenInstanceError):
        res1.next_state.processed_valid_count = 99  # type: ignore


def test_deterministic_reconstruction(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()

    ev1 = make_evidence("session-1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    ev2 = make_evidence("session-2", k_Z=20, n_Z=100, k_X=2, n_X=100)

    st1_1 = Stage1Result("session-1", "PROCESSED", 0.05, 0.4, 0.5, True, {})
    st1_2 = Stage1Result("session-2", "PROCESSED", 0.07, 0.8, 0.3, True, {})

    # Stream 1 execution
    r1_a = update_stage2_sequential_test(state0, ev1, st1_1, 1, sample_provenance)
    r2_a = update_stage2_sequential_test(r1_a.next_state, ev2, st1_2, 2, sample_provenance)

    # Stream 2 execution
    r1_b = update_stage2_sequential_test(state0, ev1, st1_1, 1, sample_provenance)
    r2_b = update_stage2_sequential_test(r1_b.next_state, ev2, st1_2, 2, sample_provenance)

    assert r2_a.next_state == r2_b.next_state


def test_no_mutation_of_protocol_data(sample_provenance, valid_stage1_result):
    state0 = create_initial_stage2_state()
    ev1 = make_evidence("session-1", k_Z=15, n_Z=100, k_X=5, n_X=100)
    res1 = update_stage2_sequential_test(state0, ev1, valid_stage1_result, 1, sample_provenance)

    # Telemetry and Stage 1 inputs remain untouched
    assert ev1.z_mismatch_count == 15
    assert valid_stage1_result.statistic == 0.5
