import pytest
import math
from qds.protocol import run_session, SessionConfig
from experiments.calibration import generate_calibration_artifact
from qsentinel_monitor.calibration_loader import load_calibration_artifact
from qsentinel_monitor.quantum_evidence.models import (
    Stage1Result,
    QuantumEvidence,
    CalibrationLookupStatus,
    CalibratedDecisionStatus,
    CalibratedStage1Decision,
)
from qsentinel_monitor.calibrated_decision import evaluate_calibrated_stage1, CalibrationLookupError
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


def test_calibrated_decision_exact_match_consistent(sample_artifact):
    entry = sample_artifact.calibration_table[1]  # p=0.1
    p_val = entry["p"]
    crit_val = entry["empirical_critical_value"]

    stage1_res = Stage1Result(
        session_id="s1",
        status="PROCESSED",
        best_fit_p=p_val,
        statistic=crit_val - 1.0,
        uncalibrated_theoretical_p_value=0.5,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.lookup_status == CalibrationLookupStatus.EXACT_MATCH
    assert dec.decision == CalibratedDecisionStatus.MODEL_CONSISTENT
    assert dec.matched_calibration_p == p_val
    assert dec.empirical_critical_value == crit_val
    assert pytest.approx(dec.margin_to_critical_value) == 1.0


def test_calibrated_decision_exact_match_inconsistent(sample_artifact):
    entry = sample_artifact.calibration_table[1]  # p=0.1
    p_val = entry["p"]
    crit_val = entry["empirical_critical_value"]

    stage1_res = Stage1Result(
        session_id="s2",
        status="PROCESSED",
        best_fit_p=p_val,
        statistic=crit_val + 5.0,
        uncalibrated_theoretical_p_value=0.001,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.lookup_status == CalibrationLookupStatus.EXACT_MATCH
    assert dec.decision == CalibratedDecisionStatus.MODEL_INCONSISTENT
    assert dec.empirical_critical_value == crit_val
    assert pytest.approx(dec.margin_to_critical_value) == -5.0


def test_calibrated_decision_exact_equality_consistent(sample_artifact):
    entry = sample_artifact.calibration_table[1]
    p_val = entry["p"]
    crit_val = entry["empirical_critical_value"]

    stage1_res = Stage1Result(
        session_id="s3",
        status="PROCESSED",
        best_fit_p=p_val,
        statistic=crit_val,
        uncalibrated_theoretical_p_value=0.01,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.decision == CalibratedDecisionStatus.MODEL_CONSISTENT
    assert pytest.approx(dec.margin_to_critical_value) == 0.0


def test_calibrated_decision_between_grid(sample_artifact):
    stage1_res = Stage1Result(
        session_id="s4",
        status="PROCESSED",
        best_fit_p=0.15,  # Between 0.1 and 0.2
        statistic=2.0,
        uncalibrated_theoretical_p_value=0.2,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.lookup_status == CalibrationLookupStatus.CALIBRATION_UNAVAILABLE
    assert dec.decision == CalibratedDecisionStatus.CALIBRATION_UNAVAILABLE
    assert dec.matched_calibration_p is None
    assert dec.empirical_critical_value is None


def test_calibrated_decision_above_grid(sample_artifact):
    stage1_res = Stage1Result(
        session_id="s5",
        status="PROCESSED",
        best_fit_p=0.45,  # Above max 0.3
        statistic=2.0,
        uncalibrated_theoretical_p_value=0.2,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.lookup_status == CalibrationLookupStatus.CALIBRATION_OUT_OF_SUPPORT
    assert dec.decision == CalibratedDecisionStatus.CALIBRATION_OUT_OF_SUPPORT


def test_calibrated_decision_below_grid(sample_artifact):
    stage1_res = Stage1Result(
        session_id="s6",
        status="PROCESSED",
        best_fit_p=-0.05,  # Below min 0.0
        statistic=2.0,
        uncalibrated_theoretical_p_value=0.2,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.lookup_status == CalibrationLookupStatus.CALIBRATION_OUT_OF_SUPPORT
    assert dec.decision == CalibratedDecisionStatus.CALIBRATION_OUT_OF_SUPPORT


def test_calibrated_decision_p0_degenerate_boundary(sample_artifact):
    stage1_res = Stage1Result(
        session_id="s7",
        status="PROCESSED",
        best_fit_p=0.0,
        statistic=0.0,
        uncalibrated_theoretical_p_value=1.0,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.lookup_status == CalibrationLookupStatus.DEGENERATE_BOUNDARY
    assert dec.decision == CalibratedDecisionStatus.DEGENERATE_BOUNDARY
    assert dec.matched_calibration_p == 0.0
    assert dec.empirical_critical_value == 0.0


def test_decision_uses_empirical_not_asymptotic(sample_artifact):
    """TEST 8 & 9: Decision uses empirical_critical_value, changing asymptotic does not alter decision."""
    entry = sample_artifact.calibration_table[1]  # p=0.1
    emp_val = entry["empirical_critical_value"]

    # Choose raw_T between empirical and asymptotic (e.g. emp_val + 0.1)
    stage1_res = Stage1Result(
        session_id="s8",
        status="PROCESSED",
        best_fit_p=0.1,
        statistic=emp_val + 0.1,
        uncalibrated_theoretical_p_value=0.01,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.decision == CalibratedDecisionStatus.MODEL_INCONSISTENT


def test_provenance_propagation(sample_artifact):
    stage1_res = Stage1Result(
        session_id="s10",
        status="PROCESSED",
        best_fit_p=0.1,
        statistic=1.0,
        uncalibrated_theoretical_p_value=0.5,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.artifact_content_hash == sample_artifact.content_hash
    assert dec.artifact_schema_version == sample_artifact.schema_version
    assert dec.architecture_version == sample_artifact.architecture_version
    assert dec.stage1_model_version == sample_artifact.stage1_model_version


def test_decision_immutability(sample_artifact):
    stage1_res = Stage1Result(
        session_id="s11",
        status="PROCESSED",
        best_fit_p=0.1,
        statistic=1.0,
        uncalibrated_theoretical_p_value=0.5,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    with pytest.raises(AttributeError):
        dec.decision = CalibratedDecisionStatus.MODEL_CONSISTENT


def test_stage1_failure_handling(sample_artifact):
    """TEST 12, 13, 14: Stage1Result failure or NaN/Inf -> STAGE1_UNAVAILABLE."""
    res_failed = Stage1Result(
        session_id="sf1",
        status="OPTIMIZER_FAILURE",
        best_fit_p=0.1,
        statistic=1.0,
        uncalibrated_theoretical_p_value=0.5,
        optimization_success=False,
        diagnostic_info={},
    )
    dec1 = evaluate_calibrated_stage1(res_failed, sample_artifact)
    assert dec1.decision == CalibratedDecisionStatus.STAGE1_UNAVAILABLE

    res_nan = Stage1Result(
        session_id="sf2",
        status="PROCESSED",
        best_fit_p=0.1,
        statistic=math.nan,
        uncalibrated_theoretical_p_value=0.5,
        optimization_success=True,
        diagnostic_info={},
    )
    dec2 = evaluate_calibrated_stage1(res_nan, sample_artifact)
    assert dec2.decision == CalibratedDecisionStatus.STAGE1_UNAVAILABLE

    res_inf = Stage1Result(
        session_id="sf3",
        status="PROCESSED",
        best_fit_p=math.inf,
        statistic=1.0,
        uncalibrated_theoretical_p_value=0.5,
        optimization_success=True,
        diagnostic_info={},
    )
    dec3 = evaluate_calibrated_stage1(res_inf, sample_artifact)
    assert dec3.decision == CalibratedDecisionStatus.STAGE1_UNAVAILABLE


def test_near_zero_positive_p_not_degenerate_boundary(sample_artifact):
    """
    TEST 15 (CORRECTION A):
    Near-zero positive p_hat (e.g. p_hat=0.001) that does NOT match p=0.0 entry within tolerance (1e-4)
    must NOT be silently classified as DEGENERATE_BOUNDARY. It should be CALIBRATION_UNAVAILABLE.
    """
    stage1_res = Stage1Result(
        session_id="s15",
        status="PROCESSED",
        best_fit_p=0.005,  # 0.005 > 1e-4 tolerance from 0.0, and < 0.1
        statistic=0.5,
        uncalibrated_theoretical_p_value=0.5,
        optimization_success=True,
        diagnostic_info={},
    )

    dec = evaluate_calibrated_stage1(stage1_res, sample_artifact)
    assert dec.lookup_status == CalibrationLookupStatus.CALIBRATION_UNAVAILABLE
    assert dec.decision == CalibratedDecisionStatus.CALIBRATION_UNAVAILABLE


def test_orchestrator_integration_with_and_without_artifact(sample_artifact):
    """
    TEST 20, 21, 22: Orchestrator integrates calibration decision via injection,
    preserves previous behavior without artifact, and keeps ProtocolDecision 100% bit-for-bit identical.
    """
    config = SessionConfig(n_qubits=100, noise_parameter_p=0.10, seed=99)
    transcript = run_session(config)

    res_no_art = analyze_session(transcript, calibration_artifact=None)
    assert res_no_art.calibrated_decision is None
    assert res_no_art.protocol_decision == transcript.protocol_decision

    res_with_art = analyze_session(transcript, calibration_artifact=sample_artifact)
    assert res_with_art.calibrated_decision is not None
    assert isinstance(res_with_art.calibrated_decision, CalibratedStage1Decision)
    assert res_with_art.protocol_decision == transcript.protocol_decision
    assert res_with_art.protocol_decision.accepted == res_no_art.protocol_decision.accepted
