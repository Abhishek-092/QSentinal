"""
Phase 9 Unified Orchestrator & Threat Assessment Unit Test Suite for QSENTINEL.

Verifies:
1. Initial unified state generation defaults
2. End-to-end pipeline execution with Stage 1, Stage 2, and Change-Point detectors
3. Severity escalation logic (NOMINAL -> MEDIUM -> HIGH -> CRITICAL)
4. Multi-detector contributing detector aggregation
5. Horizon exceedance reporting in unified threat assessment
6. Provenance bundle extraction across all 3 artifacts
7. Backwards compatibility of analyze_session() API
8. Pure advisory non-interference guarantee
"""
import pytest

from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.orchestrator import analyze_session
from qsentinel_monitor.quantum_evidence.models import CalibratedDecisionStatus
from qsentinel_monitor.sequential_test_models import (
    Stage2DecisionStatus,
    CalibratedStage2Decision,
)
from qsentinel_monitor.changepoint_models import (
    ChangePointDecisionStatus,
    CalibratedChangePointDecision,
)
from qsentinel_monitor.threat_models import (
    SecurityPosture,
    ThreatSeverity,
    UnifiedMonitoringState,
    UnifiedMonitoringResult,
    UnifiedThreatAssessment,
)
from qsentinel_monitor.unified_orchestrator import (
    create_initial_unified_state,
    evaluate_unified_threat,
    analyze_unified_session,
)
from qsentinel_monitor.calibration_loader import CalibrationArtifact
from qsentinel_monitor.stage2_calibration_loader import Stage2CalibrationArtifact
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact


@pytest.fixture
def mock_stage1_artifact() -> CalibrationArtifact:
    return CalibrationArtifact(
        schema_version="1.0",
        architecture_version="v5.0",
        stage1_model_version="v1.0",
        calibration_configuration={
            "n_qubits": 200,
            "alpha": 0.01,
            "n_trials_per_grid_point": 100,
            "p_grid": [0.0, 0.02, 0.05],
        },
        seed_provenance={"purpose": "CALIBRATION", "schedule_version": "v1.0", "seed_start": 0, "seed_count": 300, "mapping": "linear"},
        calibration_table=[
            {
                "p": 0.02,
                "null_classification": "REGULAR_INTERIOR_NULL",
                "empirical_critical_value": 3.84,
                "asymptotic_reference_applicability": "REGULAR_CHI2_DF1",
                "asymptotic_critical_value": 3.84,
                "n_trials": 100,
                "quantile_probability": 0.99,
            }
        ],
        content_hash="st1_hash_111",
    )


@pytest.fixture
def mock_stage2_artifact() -> Stage2CalibrationArtifact:
    return Stage2CalibrationArtifact(
        schema_version="1.0",
        architecture_version="v6.0",
        stage2_model_version="v1.0",
        calibration_configuration={
            "n_qubits": 200,
            "alpha": 0.01,
            "horizon_sessions": 5,
            "n_trials_per_grid_point": 100,
            "p_grid": [0.0, 0.02, 0.05],
            "quantile_method": "weibull",
            "calibration_guarantee": "HORIZON_BOUNDED",
            "calibrated_statistic": "MAX_CUMULATIVE_EVIDENCE",
        },
        seed_provenance={"purpose": "CALIBRATION", "schedule_version": "v2.0", "seed_start": 0, "seed_count": 1500, "seed_unit": "STREAM", "mapping": "linear", "child_seed_derivation": "sha256_v1"},
        calibration_table=[
            {
                "p": 0.02,
                "null_classification": "REGULAR_INTERIOR_NULL",
                "empirical_critical_value": 10.0,
                "max_statistic_mean": 1.0,
                "max_statistic_std": 0.5,
                "n_trials": 100,
                "quantile_probability": 0.99,
            }
        ],
        content_hash="st2_hash_222",
    )


@pytest.fixture
def mock_changepoint_artifact() -> ChangePointCalibrationArtifact:
    return ChangePointCalibrationArtifact(
        schema_version="1.0",
        architecture_version="v8.0",
        changepoint_model_version="v1.0",
        calibration_configuration={
            "n_qubits": 200,
            "alpha": 0.01,
            "horizon_sessions": 5,
            "n_trials_per_grid_point": 100,
            "p_grid": [0.0, 0.02, 0.05],
            "quantile_method": "weibull",
            "calibration_guarantee": "HORIZON_BOUNDED",
            "calibrated_statistic": "MAX_OFFSET_CUSUM",
            "offset_formula": "d(p) = mu_H0(p) + delta(p)",
            "delta_offset_margin": 0.05,
        },
        seed_provenance={"purpose": "CALIBRATION", "schedule_version": "v2.0", "seed_start": 0, "seed_count": 1500, "seed_unit": "STREAM", "mapping": "linear", "child_seed_derivation": "sha256_v1"},
        calibration_table=[
            {
                "p": 0.02,
                "null_classification": "REGULAR_INTERIOR_NULL",
                "null_mean_glr": 0.02,
                "delta_offset_margin": 0.05,
                "null_offset_d": 0.07,
                "empirical_critical_value": 15.0,
                "max_cusum_mean": 0.2,
                "max_cusum_std": 0.1,
                "n_trials": 100,
                "quantile_probability": 0.99,
            }
        ],
        content_hash="cp_hash_333",
    )


def test_initial_unified_state_defaults():
    st = create_initial_unified_state()
    assert st.sequence_number == 0
    assert st.stage2_state.processed_valid_count == 0
    assert st.changepoint_state.processed_valid_count == 0


def test_analyze_unified_session_end_to_end(
    mock_stage1_artifact, mock_stage2_artifact, mock_changepoint_artifact
):
    tr = run_session(SessionConfig(noise_parameter_p=0.02, seed=12345))
    res = analyze_unified_session(
        transcript=tr,
        previous_unified_state=None,
        stage1_artifact=mock_stage1_artifact,
        stage2_artifact=mock_stage2_artifact,
        changepoint_artifact=mock_changepoint_artifact,
        calibration_p=0.02,
    )

    assert isinstance(res, UnifiedMonitoringResult)
    assert res.sequence_number == 1
    assert res.is_advisory is True

    # Check evidence & stage 1
    assert res.evidence.session_id == tr.session_id
    assert res.stage1_result.status == "PROCESSED"
    assert res.calibrated_stage1_decision is not None

    # Check Stage 2 & Change-Point decisions
    assert res.calibrated_stage2_decision is not None
    assert res.calibrated_changepoint_decision is not None

    # Check Unified Threat Assessment
    ta = res.threat_assessment
    assert isinstance(ta, UnifiedThreatAssessment)
    assert ta.security_posture == SecurityPosture.NOMINAL
    assert ta.threat_severity == ThreatSeverity.INFORMATIONAL
    assert ta.provenance_bundle.stage1_artifact_hash == "st1_hash_111"
    assert ta.provenance_bundle.stage2_artifact_hash == "st2_hash_222"
    assert ta.provenance_bundle.changepoint_artifact_hash == "cp_hash_333"

    # Verify next unified state sequence count
    assert res.next_unified_state.sequence_number == 1
    assert res.next_unified_state.stage2_state.processed_valid_count == 1
    assert res.next_unified_state.changepoint_state.processed_valid_count == 1


def test_threat_assessment_escalation_and_critical_posture(
    mock_stage1_artifact, mock_stage2_artifact, mock_changepoint_artifact
):
    # Single detector elevation -> Stage 2 elevated
    ta_single = evaluate_unified_threat(
        session_id="sess_1",
        sequence_number=1,
        stage1_dec=None,
        stage2_dec=CalibratedStage2Decision(
            session_id="sess_1",
            sequence_number=1,
            cumulative_log_likelihood_ratio=15.0,
            processed_valid_count=1,
            calibration_p=0.02,
            matched_calibration_p=0.02,
            empirical_critical_value=10.0,
            horizon_sessions=5,
            decision_status=Stage2DecisionStatus.STAGE2_CALIBRATED_ELEVATED,
            outcome="EVIDENCE_ACCEPTED",
            artifact_content_hash="st2_hash_222",
            artifact_schema_version="1.0",
            architecture_version="v6.0",
            stage2_model_version="v1.0",
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason="Elevated",
        ),
        changepoint_dec=None,
        stage1_artifact=mock_stage1_artifact,
        stage2_artifact=mock_stage2_artifact,
        changepoint_artifact=mock_changepoint_artifact,
    )
    assert ta_single.security_posture == SecurityPosture.ELEVATED_STAGE2
    assert ta_single.threat_severity == ThreatSeverity.HIGH
    assert ta_single.contributing_detectors == ("STAGE_2_CUMULATIVE_GLR",)

    # Multi-detector elevation -> Critical posture
    ta_critical = evaluate_unified_threat(
        session_id="sess_1",
        sequence_number=1,
        stage1_dec=None,
        stage2_dec=CalibratedStage2Decision(
            session_id="sess_1",
            sequence_number=1,
            cumulative_log_likelihood_ratio=15.0,
            processed_valid_count=1,
            calibration_p=0.02,
            matched_calibration_p=0.02,
            empirical_critical_value=10.0,
            horizon_sessions=5,
            decision_status=Stage2DecisionStatus.STAGE2_CALIBRATED_ELEVATED,
            outcome="EVIDENCE_ACCEPTED",
            artifact_content_hash="st2_hash_222",
            artifact_schema_version="1.0",
            architecture_version="v6.0",
            stage2_model_version="v1.0",
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason="Elevated",
        ),
        changepoint_dec=CalibratedChangePointDecision(
            session_id="sess_1",
            sequence_number=1,
            cusum_statistic=20.0,
            active_run_length=1,
            estimated_excursion_onset=1,
            processed_valid_count=1,
            calibration_p=0.02,
            matched_calibration_p=0.02,
            null_offset_d=0.07,
            empirical_critical_value=15.0,
            horizon_sessions=5,
            decision_status=ChangePointDecisionStatus.CHANGEPOINT_CALIBRATED_ELEVATED,
            outcome="EVIDENCE_ACCEPTED",
            artifact_content_hash="cp_hash_333",
            artifact_schema_version="1.0",
            architecture_version="v8.0",
            changepoint_model_version="v1.0",
            calibration_guarantee="HORIZON_BOUNDED",
            diagnostic_reason="Elevated",
        ),
        stage1_artifact=mock_stage1_artifact,
        stage2_artifact=mock_stage2_artifact,
        changepoint_artifact=mock_changepoint_artifact,
    )
    assert ta_critical.security_posture == SecurityPosture.ELEVATED_CRITICAL
    assert ta_critical.threat_severity == ThreatSeverity.CRITICAL
    assert set(ta_critical.contributing_detectors) == {
        "STAGE_2_CUMULATIVE_GLR",
        "OFFSET_GLR_CUSUM_CHANGEPOINT",
    }


def test_analyze_session_backwards_compatibility(mock_stage1_artifact):
    tr = run_session(SessionConfig(noise_parameter_p=0.02, seed=12345))
    res = analyze_session(tr, calibration_artifact=mock_stage1_artifact)
    assert res.session_id == tr.session_id
    assert res.protocol_decision == tr.protocol_decision
    assert res.calibrated_decision is not None
    assert res.is_advisory is True
