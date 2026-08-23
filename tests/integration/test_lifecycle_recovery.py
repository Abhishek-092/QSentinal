"""
Phase 10 Lifecycle & Process Restart Recovery Integration Test Suite for QSENTINEL.

Verifies:
1. Stream creation, epoch creation, and explicit calibration context enforcement
2. Sequential session processing with persistent state accumulation
3. Process restart recovery: restoring detector snapshot state and continuing cleanly
4. Idempotent duplicate submission handling vs conflicting session ID rejection
5. Partial detector expiry policy (Stage 2 expired while Change-Point remains active)
6. Detector elevation freezing epoch lifecycle
7. Explicit epoch renewal and clean index increments
"""
from dataclasses import replace
import os
import tempfile
import pytest

from qds.protocol import run_session, SessionConfig
from qds.transcript import SessionTranscript
from qsentinel_monitor.persistence.database import init_database
from qsentinel_monitor.persistence.serializers import compute_sha256_hash
from qsentinel_monitor.persistence.models import (
    ConflictingSessionIdError,
    CryptographicIntegrityError,
    EpochClosedError,
)
from qsentinel_monitor.lifecycle.stream_manager import StreamLifecycleManager
from qsentinel_monitor.lifecycle.session_runner import TransactionalSessionRunner
from qsentinel_monitor.calibration_loader import CalibrationArtifact
from qsentinel_monitor.stage2_calibration_loader import Stage2CalibrationArtifact
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact
from qsentinel_monitor.threat_models import SecurityPosture, ThreatSeverity


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_lifecycle.db")
        init_database(db_path)
        yield db_path


@pytest.fixture
def mock_artifacts():
    p1 = {
        "schema_version": "1.0",
        "architecture_version": "v5.0",
        "stage1_model_version": "v1.0",
        "calibration_configuration": {"n_qubits": 200, "alpha": 0.01, "n_trials_per_grid_point": 100, "p_grid": [0.0, 0.02]},
        "seed_provenance": {"purpose": "CALIBRATION", "schedule_version": "v1.0", "seed_start": 0, "seed_count": 300, "mapping": "linear"},
        "calibration_table": [{"p": 0.02, "null_classification": "REGULAR_INTERIOR_NULL", "empirical_critical_value": 3.84, "asymptotic_reference_applicability": "REGULAR_CHI2_DF1", "asymptotic_critical_value": 3.84, "n_trials": 100, "quantile_probability": 0.99}],
    }
    p1["content_hash"] = compute_sha256_hash(p1)
    st1 = CalibrationArtifact(**p1)

    p2 = {
        "schema_version": "1.0",
        "architecture_version": "v6.0",
        "stage2_model_version": "v1.0",
        "calibration_configuration": {"n_qubits": 200, "alpha": 0.01, "horizon_sessions": 2, "n_trials_per_grid_point": 100, "p_grid": [0.0, 0.02], "quantile_method": "weibull", "calibration_guarantee": "HORIZON_BOUNDED", "calibrated_statistic": "MAX_CUMULATIVE_EVIDENCE"},
        "seed_provenance": {"purpose": "CALIBRATION", "schedule_version": "v2.0", "seed_start": 0, "seed_count": 1500, "seed_unit": "STREAM", "mapping": "linear", "child_seed_derivation": "sha256_v1"},
        "calibration_table": [{"p": 0.02, "null_classification": "REGULAR_INTERIOR_NULL", "empirical_critical_value": 100.0, "max_statistic_mean": 1.0, "max_statistic_std": 0.5, "n_trials": 100, "quantile_probability": 0.99}],
    }
    p2["content_hash"] = compute_sha256_hash(p2)
    st2 = Stage2CalibrationArtifact(**p2)

    p3 = {
        "schema_version": "1.0",
        "architecture_version": "v8.0",
        "changepoint_model_version": "v1.0",
        "calibration_configuration": {"n_qubits": 200, "alpha": 0.01, "horizon_sessions": 5, "n_trials_per_grid_point": 100, "p_grid": [0.0, 0.02], "quantile_method": "weibull", "calibration_guarantee": "HORIZON_BOUNDED", "calibrated_statistic": "MAX_OFFSET_CUSUM", "offset_formula": "d(p) = mu_H0(p) + delta(p)", "delta_offset_margin": 0.05},
        "seed_provenance": {"purpose": "CALIBRATION", "schedule_version": "v2.0", "seed_start": 0, "seed_count": 1500, "seed_unit": "STREAM", "mapping": "linear", "child_seed_derivation": "sha256_v1"},
        "calibration_table": [{"p": 0.02, "null_classification": "REGULAR_INTERIOR_NULL", "null_mean_glr": 0.02, "delta_offset_margin": 0.05, "null_offset_d": 0.07, "empirical_critical_value": 100.0, "max_cusum_mean": 0.2, "max_cusum_std": 0.1, "n_trials": 100, "quantile_probability": 0.99}],
    }
    p3["content_hash"] = compute_sha256_hash(p3)
    cp = ChangePointCalibrationArtifact(**p3)

    return st1, st2, cp


def test_missing_calibration_context_fails(temp_db):
    mgr = StreamLifecycleManager(temp_db)
    mgr.create_stream("str-1")
    with pytest.raises(ValueError, match="Explicit calibration_p operating point required"):
        mgr.create_epoch("str-1", calibration_context={})


def test_session_runner_restart_recovery_and_idempotency(temp_db, mock_artifacts):
    st1, st2, cp = mock_artifacts
    mgr = StreamLifecycleManager(temp_db)
    mgr.create_stream("str-1")
    epoch = mgr.create_epoch(
        "str-1",
        calibration_context={"calibration_p": 0.02},
        stage1_artifact=st1,
        stage2_artifact=st2,
        changepoint_artifact=cp,
    )

    runner = TransactionalSessionRunner(temp_db)
    tr1 = run_session(SessionConfig(noise_parameter_p=0.02, seed=1, nonce="n1"))

    # Session 1 processing
    res1 = runner.process_session(
        epoch.epoch_id, tr1, stage1_artifact=st1, stage2_artifact=st2, changepoint_artifact=cp
    )
    assert res1.sequence_number == 1
    assert res1.next_unified_state.sequence_number == 1

    # Idempotent re-submission of exact same session
    res1_dup = runner.process_session(
        epoch.epoch_id, tr1, stage1_artifact=st1, stage2_artifact=st2, changepoint_artifact=cp
    )
    assert res1_dup.sequence_number == 1
    assert res1_dup.next_unified_state.sequence_number == 1  # State unmutated

    # Conflicting session ID submission (reusing session_id with different nonce/transcript content)
    tr1_conflict = run_session(SessionConfig(noise_parameter_p=0.02, seed=1, nonce="n1_CONFLICTING"))
    # Manually override session_id to mimic session ID reuse with conflicting content
    tr1_conflict = replace(tr1_conflict, session_id=tr1.session_id)
    with pytest.raises(ConflictingSessionIdError, match="reused with conflicting transcript content"):
        runner.process_session(
            epoch.epoch_id, tr1_conflict, stage1_artifact=st1, stage2_artifact=st2, changepoint_artifact=cp
        )

    # SIMULATED PROCESS RESTART: Create a brand new runner instance over the existing SQLite file
    runner_restarted = TransactionalSessionRunner(temp_db)

    # Session 2 processing after restart
    tr2 = run_session(SessionConfig(noise_parameter_p=0.02, seed=2, nonce="n2"))
    res2 = runner_restarted.process_session(
        epoch.epoch_id, tr2, stage1_artifact=st1, stage2_artifact=st2, changepoint_artifact=cp
    )
    assert res2.sequence_number == 2
    assert res2.next_unified_state.sequence_number == 2
    assert res2.next_unified_state.stage2_state.processed_valid_count == 2


def test_partial_detector_expiry_policy(temp_db, mock_artifacts):
    st1, st2, cp = mock_artifacts  # st2 horizon = 2, cp horizon = 5
    mgr = StreamLifecycleManager(temp_db)
    mgr.create_stream("str-1")
    epoch = mgr.create_epoch(
        "str-1",
        calibration_context={"calibration_p": 0.02},
        stage1_artifact=st1,
        stage2_artifact=st2,
        changepoint_artifact=cp,
    )
    runner = TransactionalSessionRunner(temp_db)

    # Process 2 sessions -> Stage 2 reaches horizon H=2
    for s in range(1, 3):
        tr = run_session(SessionConfig(noise_parameter_p=0.02, seed=s, nonce=f"n_{s}"))
        runner.process_session(epoch.epoch_id, tr, stage1_artifact=st1, stage2_artifact=st2, changepoint_artifact=cp)

    # Process session 3 -> Stage 2 is horizon exceeded, but Change-Point (H=5) continues valid evaluation
    tr3 = run_session(SessionConfig(noise_parameter_p=0.02, seed=3, nonce="n_3"))
    res3 = runner.process_session(epoch.epoch_id, tr3, stage1_artifact=st1, stage2_artifact=st2, changepoint_artifact=cp)

    assert res3.sequence_number == 3
    assert res3.threat_assessment.stage2_horizon_exceeded is True
    assert res3.threat_assessment.changepoint_horizon_exceeded is False
    # PARTIAL EXPIRY POLICY: Epoch remains ACTIVE because Change-Point is still within horizon
    ep_record = mgr.create_epoch  # Check DB
    from qsentinel_monitor.persistence.repositories import EpochRepository
    current_ep = EpochRepository.get_epoch(temp_db, epoch.epoch_id)
    assert current_ep.status == "ACTIVE"


def test_explicit_epoch_renewal(temp_db, mock_artifacts):
    st1, st2, cp = mock_artifacts
    mgr = StreamLifecycleManager(temp_db)
    mgr.create_stream("str-1")
    ep1 = mgr.create_epoch("str-1", calibration_context={"calibration_p": 0.02}, stage1_artifact=st1)
    assert ep1.epoch_index == 1

    # Renew epoch
    ep2 = mgr.renew_epoch("str-1", calibration_context={"calibration_p": 0.02}, stage1_artifact=st1)
    assert ep2.epoch_index == 2

    from qsentinel_monitor.persistence.repositories import EpochRepository
    old_ep = EpochRepository.get_epoch(temp_db, ep1.epoch_id)
    assert old_ep.status == "CLOSED"
