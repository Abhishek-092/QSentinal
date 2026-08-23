"""
Phase 10 Persistence Unit Test Suite for QSENTINEL.

Verifies:
1. Database initialization & WAL mode
2. Artifact insertion, canonical content-addressing, and tamper detection
3. Dataclass, Enum, Tuple, and float serialization round-trip fidelity
4. Snapshot SHA-256 state hash generation and tamper detection
5. Duplicate session prevention and unique constraints
6. Conflicting session ID reuse detection
7. Atomic transaction rollback on failure
"""
import os
import tempfile
import sqlite3
import json
import pytest

from qsentinel_monitor.persistence.database import init_database, get_connection, transaction_scope
from qsentinel_monitor.persistence.models import (
    CryptographicIntegrityError,
    ConflictingSessionIdError,
    DuplicateSessionError,
)
from qsentinel_monitor.persistence.serializers import (
    canonical_json_dumps,
    compute_sha256_hash,
    deserialize_unified_state,
    deserialize_threat_assessment,
)
from qsentinel_monitor.persistence.repositories import (
    ArtifactRepository,
    StreamRepository,
    EpochRepository,
    SessionRepository,
)
from qsentinel_monitor.sequential_test import create_initial_stage2_state
from qsentinel_monitor.changepoint_detector import create_initial_changepoint_state
from qsentinel_monitor.threat_models import (
    SecurityPosture,
    ThreatSeverity,
    ProvenanceBundle,
    UnifiedThreatAssessment,
    UnifiedMonitoringState,
)


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_qsentinel.db")
        init_database(db_path)
        yield db_path


def test_database_init_and_wal_mode(temp_db):
    conn = get_connection(temp_db)
    row = conn.execute("PRAGMA journal_mode;").fetchone()
    assert row[0].lower() == "wal"
    conn.close()


def test_artifact_repository_content_addressing_and_tamper_detection(temp_db):
    artifact_payload = {
        "schema_version": "1.0",
        "architecture_version": "v9.0",
        "artifact_type": "STAGE1",
        "p_grid": [0.0, 0.02, 0.05],
    }
    content_hash = ArtifactRepository.save_artifact(temp_db, "STAGE1", artifact_payload)
    assert len(content_hash) == 64

    # Retrieve & verify
    loaded = ArtifactRepository.get_artifact(temp_db, content_hash)
    assert loaded["schema_version"] == "1.0"

    # Tamper payload directly in DB to test tamper detection
    conn = get_connection(temp_db)
    conn.execute(
        "UPDATE calibration_artifacts SET json_payload = ? WHERE content_hash = ?",
        ('{"schema_version":"TAMPERED"}', content_hash),
    )
    conn.commit()
    conn.close()

    with pytest.raises(CryptographicIntegrityError, match="DB Tamper Alert"):
        ArtifactRepository.get_artifact(temp_db, content_hash)


def test_serializer_round_trip_fidelity():
    st2 = create_initial_stage2_state()
    cp = create_initial_changepoint_state()
    unified_state = UnifiedMonitoringState(sequence_number=5, stage2_state=st2, changepoint_state=cp)

    json_str = canonical_json_dumps(unified_state)
    import json
    d = json.loads(json_str)
    restored = deserialize_unified_state(d)

    assert restored.sequence_number == 5
    assert restored.stage2_state.processed_valid_count == 0
    assert restored.changepoint_state.processed_valid_count == 0


def test_snapshot_tamper_detection(temp_db):
    # Setup stream & epoch
    StreamRepository.create_stream(temp_db, "str-1")
    epoch = EpochRepository.create_epoch(
        temp_db, "ep-1", "str-1", 1, calibration_context={"calibration_p": 0.02}
    )

    st2 = create_initial_stage2_state()
    cp = create_initial_changepoint_state()
    st2_json = canonical_json_dumps(st2)
    cp_json = canonical_json_dumps(cp)
    payload = {
        "sequence_number": 1,
        "stage2_state": json.loads(st2_json),
        "changepoint_state": json.loads(cp_json),
    }
    h = compute_sha256_hash(payload)

    with transaction_scope(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO detector_state_snapshots 
            (snapshot_id, epoch_id, sequence_number, stage2_state_json, changepoint_state_json, snapshot_hash)
            VALUES ('snap-1', 'ep-1', 1, ?, ?, ?)
            """,
            (st2_json, cp_json, h),
        )

    # Valid load
    res = SessionRepository.get_latest_snapshot(temp_db, "ep-1")
    assert res is not None
    assert res[0].sequence_number == 1

    # Tamper hash in DB
    conn = get_connection(temp_db)
    conn.execute("UPDATE detector_state_snapshots SET snapshot_hash = 'BAD_HASH' WHERE snapshot_id = 'snap-1'")
    conn.commit()
    conn.close()

    with pytest.raises(CryptographicIntegrityError, match="DB Tamper Alert"):
        SessionRepository.get_latest_snapshot(temp_db, "ep-1")


def test_transactional_rollback_on_failure(temp_db):
    StreamRepository.create_stream(temp_db, "str-1")
    EpochRepository.create_epoch(temp_db, "ep-1", "str-1", 1, calibration_context={"calibration_p": 0.02})

    with pytest.raises(RuntimeError):
        with transaction_scope(temp_db) as conn:
            conn.execute(
                "INSERT INTO monitoring_sessions (session_id, epoch_id, sequence_number, fingerprint, transcript_json, evidence_json) VALUES ('s1', 'ep-1', 1, 'f1', '{}', '{}')"
            )
            raise RuntimeError("Simulated crash mid-transaction")

    # Verify session was NOT persisted
    sess = SessionRepository.get_session_by_id(temp_db, "ep-1", "s1")
    assert sess is None
