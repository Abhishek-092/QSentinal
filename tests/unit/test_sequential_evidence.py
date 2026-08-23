import pytest
import math
from qds.protocol import run_session, SessionConfig
from experiments.calibration import generate_calibration_artifact
from qsentinel_monitor.calibration_loader import load_calibration_artifact
from qsentinel_monitor.quantum_evidence.models import (
    Stage1Result,
    CalibrationLookupStatus,
    CalibratedDecisionStatus,
    CalibratedStage1Decision,
)
from qsentinel_monitor.calibrated_decision import evaluate_calibrated_stage1
from qsentinel_monitor.sequential_evidence_models import (
    SequentialEvidenceState,
    SequentialDecisionStatus,
    SessionProcessingOutcome,
    ProvenanceIdentity,
)
from qsentinel_monitor.sequential_evidence import (
    create_initial_sequential_state,
    update_sequential_evidence,
)
from qsentinel_monitor.orchestrator import analyze_session


@pytest.fixture
def sample_artifact():
    art_dict = generate_calibration_artifact(
        p_grid=[0.0, 0.1, 0.2, 0.3],
        n_qubits=200,
        alpha=0.01,
        n_trials_per_grid_point=20,
    )
    return load_calibration_artifact(art_dict)


def make_decision(session_id: str, p_hat: float, raw_T: float, crit_val: float = 6.82, artifact_hash: str = "hash1"):
    return CalibratedStage1Decision(
        session_id=session_id,
        raw_statistic_t=raw_T,
        fitted_p_hat=p_hat,
        lookup_status=CalibrationLookupStatus.EXACT_MATCH,
        decision=CalibratedDecisionStatus.MODEL_CONSISTENT if raw_T <= crit_val else CalibratedDecisionStatus.MODEL_INCONSISTENT,
        matched_calibration_p=p_hat,
        empirical_critical_value=crit_val,
        asymptotic_critical_value=6.635,
        margin_to_critical_value=crit_val - raw_T,
        artifact_content_hash=artifact_hash,
        artifact_schema_version="1.0",
        architecture_version="v5.0",
        stage1_model_version="v1.0",
        diagnostic_reason="test",
    )


# 1. CORE SEQUENTIAL BEHAVIOR
def test_initial_state_creation():
    state = create_initial_sequential_state()
    assert state.cumulative_evidence == 0.0
    assert state.processed_valid_count == 0
    assert state.skipped_session_count == 0
    assert state.last_accepted_session_id is None
    assert state.decision_status == SequentialDecisionStatus.SEQUENTIAL_UNINITIALIZED
    assert state.history_session_ids == ()


def test_first_valid_session_advancement():
    s0 = create_initial_sequential_state()
    d1 = make_decision("s1", p_hat=0.1, raw_T=8.82, crit_val=6.82)  # delta = +2.0
    res = update_sequential_evidence(s0, d1)

    assert res.outcome == SessionProcessingOutcome.EVIDENCE_ACCEPTED
    assert res.evidence_delta == 2.0
    assert res.next_state.cumulative_evidence == 2.0
    assert res.next_state.processed_valid_count == 1
    assert res.next_state.last_accepted_session_id == "s1"
    assert res.next_state.provenance_identity.artifact_content_hash == "hash1"


def test_repeated_valid_evidence_accumulation():
    s0 = create_initial_sequential_state()
    d1 = make_decision("s1", p_hat=0.1, raw_T=8.82, crit_val=6.82)  # +2.0
    d2 = make_decision("s2", p_hat=0.1, raw_T=11.82, crit_val=6.82) # +5.0

    r1 = update_sequential_evidence(s0, d1)
    r2 = update_sequential_evidence(r1.next_state, d2)

    assert r2.outcome == SessionProcessingOutcome.EVIDENCE_ACCEPTED
    assert r2.evidence_delta == 5.0
    assert r2.next_state.cumulative_evidence == 7.0
    assert r2.next_state.processed_valid_count == 2
    assert r2.next_state.history_session_ids == ("s1", "s2")


def test_sequential_decision_transition_to_elevated():
    s0 = create_initial_sequential_state()
    d1 = make_decision("s1", p_hat=0.1, raw_T=26.82, crit_val=6.82) # +20.0 (> threshold 15.0)
    res = update_sequential_evidence(s0, d1, threshold_t_seq=15.0)

    assert res.next_state.decision_status == SequentialDecisionStatus.SEQUENTIAL_EVIDENCE_ELEVATED


# 2. IMMUTABILITY
def test_state_immutability():
    s0 = create_initial_sequential_state()
    d1 = make_decision("s1", p_hat=0.1, raw_T=8.82, crit_val=6.82)
    res = update_sequential_evidence(s0, d1)

    # Assert s0 was not mutated
    assert s0.cumulative_evidence == 0.0
    assert s0.processed_valid_count == 0
    assert s0.last_accepted_session_id is None

    # Assert frozen error on mutation attempt
    with pytest.raises(AttributeError):
        res.next_state.cumulative_evidence = 999.0


# 3. DETERMINISM
def test_determinism_and_reconstruction():
    d1 = make_decision("s1", p_hat=0.1, raw_T=8.82, crit_val=6.82)
    d2 = make_decision("s2", p_hat=0.1, raw_T=9.82, crit_val=6.82)

    s0 = create_initial_sequential_state()
    r1 = update_sequential_evidence(s0, d1)
    r2 = update_sequential_evidence(r1.next_state, d2)

    # Second run
    s0_b = create_initial_sequential_state()
    r1_b = update_sequential_evidence(s0_b, d1)
    r2_b = update_sequential_evidence(r1_b.next_state, d2)

    assert r2.next_state == r2_b.next_state


# 4. IDEMPOTENCY & DUPLICATE PROTECTION
def test_duplicate_session_rejection():
    s0 = create_initial_sequential_state()
    d1 = make_decision("s1", p_hat=0.1, raw_T=8.82, crit_val=6.82)
    r1 = update_sequential_evidence(s0, d1)

    # Submit s1 again
    r2 = update_sequential_evidence(r1.next_state, d1)

    assert r2.outcome == SessionProcessingOutcome.DUPLICATE_SESSION
    assert r2.evidence_delta == 0.0
    assert r2.next_state == r1.next_state  # State unchanged!


# 5. ORDERING ENFORCEMENT
def test_out_of_order_session_rejection():
    s0 = create_initial_sequential_state()
    d1 = make_decision("s1", p_hat=0.1, raw_T=8.82, crit_val=6.82)
    d2 = make_decision("s2", p_hat=0.1, raw_T=9.82, crit_val=6.82)

    r1 = update_sequential_evidence(s0, d1, sequence_number=10)
    # Submit d2 with sequence_number 5 <= 10
    r2 = update_sequential_evidence(r1.next_state, d2, sequence_number=5)

    assert r2.outcome == SessionProcessingOutcome.OUT_OF_ORDER_SESSION
    assert r2.evidence_delta == 0.0
    assert r2.next_state == r1.next_state


# 6. PROVENANCE COMPATIBILITY
def test_incompatible_provenance_rejection():
    s0 = create_initial_sequential_state()
    d1 = make_decision("s1", p_hat=0.1, raw_T=8.82, crit_val=6.82, artifact_hash="hash1")
    d2 = make_decision("s2", p_hat=0.1, raw_T=9.82, crit_val=6.82, artifact_hash="hash2_DIFFERENT")

    r1 = update_sequential_evidence(s0, d1)
    r2 = update_sequential_evidence(r1.next_state, d2)

    assert r2.outcome == SessionProcessingOutcome.INCOMPATIBLE_PROVENANCE
    assert r2.evidence_delta == 0.0
    assert r2.next_state == r1.next_state


# 7. INVALID AND NON-CONTRIBUTING INPUTS
def test_non_contributing_decisions_skipped():
    s0 = create_initial_sequential_state()

    # Stage1 unavailable
    d_unavail = CalibratedStage1Decision(
        session_id="su", raw_statistic_t=0.0, fitted_p_hat=0.0,
        lookup_status=CalibrationLookupStatus.STAGE1_UNAVAILABLE,
        decision=CalibratedDecisionStatus.STAGE1_UNAVAILABLE,
        matched_calibration_p=None, empirical_critical_value=None,
        asymptotic_critical_value=None, margin_to_critical_value=None,
        artifact_content_hash="hash1", artifact_schema_version="1.0",
        architecture_version="v5.0", stage1_model_version="v1.0", diagnostic_reason="err"
    )
    r_unavail = update_sequential_evidence(s0, d_unavail)
    assert r_unavail.outcome == SessionProcessingOutcome.UNAVAILABLE_STAGE1
    assert r_unavail.next_state.skipped_session_count == 1
    assert r_unavail.next_state.cumulative_evidence == 0.0

    # Calibration unavailable
    d_calib_unavail = CalibratedStage1Decision(
        session_id="scu", raw_statistic_t=2.0, fitted_p_hat=0.15,
        lookup_status=CalibrationLookupStatus.CALIBRATION_UNAVAILABLE,
        decision=CalibratedDecisionStatus.CALIBRATION_UNAVAILABLE,
        matched_calibration_p=None, empirical_critical_value=None,
        asymptotic_critical_value=None, margin_to_critical_value=None,
        artifact_content_hash="hash1", artifact_schema_version="1.0",
        architecture_version="v5.0", stage1_model_version="v1.0", diagnostic_reason="err"
    )
    r_calib_unavail = update_sequential_evidence(s0, d_calib_unavail)
    assert r_calib_unavail.outcome == SessionProcessingOutcome.UNAVAILABLE_CALIBRATION
    assert r_calib_unavail.next_state.skipped_session_count == 1

    # Degenerate p=0 boundary
    d_p0 = CalibratedStage1Decision(
        session_id="sp0", raw_statistic_t=0.0, fitted_p_hat=0.0,
        lookup_status=CalibrationLookupStatus.DEGENERATE_BOUNDARY,
        decision=CalibratedDecisionStatus.DEGENERATE_BOUNDARY,
        matched_calibration_p=0.0, empirical_critical_value=0.0,
        asymptotic_critical_value=None, margin_to_critical_value=0.0,
        artifact_content_hash="hash1", artifact_schema_version="1.0",
        architecture_version="v5.0", stage1_model_version="v1.0", diagnostic_reason="p=0"
    )
    r_p0 = update_sequential_evidence(s0, d_p0)
    assert r_p0.outcome == SessionProcessingOutcome.UNAVAILABLE_CALIBRATION
    assert r_p0.next_state.skipped_session_count == 1


# 8. NON-INTERFERENCE
def test_sequential_monitoring_non_interference():
    config = SessionConfig(n_qubits=100, noise_parameter_p=0.1, seed=42)
    transcript = run_session(config)
    res = analyze_session(transcript)

    assert res.protocol_decision == transcript.protocol_decision
    assert res.protocol_decision.accepted is True
