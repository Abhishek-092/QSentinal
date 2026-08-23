"""
Phase 10 Repository Classes for SQLite Data Access in QSENTINEL.

Provides clean repository pattern abstractions over SQLite tables for:
- Calibration Artifacts (Content-addressed store with hash verification)
- Monitoring Streams
- Monitoring Epochs
- Session Ledger & Duplicate/Conflict Prevention
- Detector State Snapshots (with cryptographic snapshot verification)
- Threat Assessment History
"""
import json
import sqlite3
from typing import Optional, List, Dict, Any, Tuple

from qsentinel_monitor.persistence.database import get_connection, transaction_scope
from qsentinel_monitor.persistence.models import (
    CryptographicIntegrityError,
    ProvenanceMismatchError,
    DuplicateSessionError,
    ConflictingSessionIdError,
    StreamRecord,
    EpochRecord,
)
from qsentinel_monitor.persistence.serializers import (
    canonical_json_dumps,
    compute_sha256_hash,
    deserialize_unified_state,
    deserialize_threat_assessment,
)
from qsentinel_monitor.threat_models import (
    UnifiedMonitoringState,
    UnifiedThreatAssessment,
)


class ArtifactRepository:
    """Repository for storing and retrieving content-addressed calibration artifacts."""

    @staticmethod
    def save_artifact(db_path: str, artifact_type: str, artifact_payload: Dict[str, Any]) -> str:
        """Stores artifact payload and returns its verified content hash."""
        payload_copy = dict(artifact_payload)
        content_hash = payload_copy.pop("content_hash", None)
        recomputed_hash = compute_sha256_hash(payload_copy)

        if content_hash is not None and content_hash != recomputed_hash:
            raise CryptographicIntegrityError(
                f"Artifact content_hash mismatch: declared {content_hash} != recomputed {recomputed_hash}"
            )

        content_hash = recomputed_hash
        payload_copy["content_hash"] = content_hash

        schema_ver = payload_copy.get("schema_version", "1.0")
        arch_ver = payload_copy.get("architecture_version", "v9.0")
        json_payload_str = canonical_json_dumps(payload_copy)

        with transaction_scope(db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO calibration_artifacts 
                (content_hash, schema_version, architecture_version, artifact_type, json_payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (content_hash, schema_ver, arch_ver, artifact_type, json_payload_str),
            )
        return content_hash

    @staticmethod
    def get_artifact(db_path: str, content_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves and cryptographically verifies a stored artifact payload."""
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT json_payload FROM calibration_artifacts WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
            if row is None:
                return None

            payload = json.loads(row["json_payload"])
            payload_copy = dict(payload)
            stored_hash = payload_copy.pop("content_hash", None)
            recomputed = compute_sha256_hash(payload_copy)

            if content_hash != stored_hash or recomputed != content_hash:
                raise CryptographicIntegrityError(
                    f"DB Tamper Alert! Artifact {content_hash} payload failed hash verification."
                )
            return payload
        finally:
            conn.close()


class StreamRepository:
    """Repository for managing long-lived monitoring streams."""

    @staticmethod
    def create_stream(db_path: str, stream_id: str, description: str = "") -> StreamRecord:
        with transaction_scope(db_path) as conn:
            conn.execute(
                "INSERT INTO monitoring_streams (stream_id, description) VALUES (?, ?)",
                (stream_id, description),
            )
        return StreamRepository.get_stream(db_path, stream_id)

    @staticmethod
    def get_stream(db_path: str, stream_id: str) -> Optional[StreamRecord]:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT stream_id, description, created_at, status FROM monitoring_streams WHERE stream_id = ?",
                (stream_id,),
            ).fetchone()
            if row is None:
                return None
            return StreamRecord(
                stream_id=row["stream_id"],
                description=row["description"],
                created_at=row["created_at"],
                status=row["status"],
            )
        finally:
            conn.close()


class EpochRepository:
    """Repository for managing multi-detector monitoring epochs."""

    @staticmethod
    def create_epoch(
        db_path: str,
        epoch_id: str,
        stream_id: str,
        epoch_index: int,
        calibration_context: Dict[str, Any],
        stage1_artifact_hash: Optional[str] = None,
        stage2_artifact_hash: Optional[str] = None,
        changepoint_artifact_hash: Optional[str] = None,
    ) -> EpochRecord:
        context_json = canonical_json_dumps(calibration_context)
        with transaction_scope(db_path) as conn:
            conn.execute(
                """
                INSERT INTO monitoring_epochs 
                (epoch_id, stream_id, epoch_index, status, stage1_artifact_hash, stage2_artifact_hash, changepoint_artifact_hash, calibration_context_json)
                VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
                """,
                (
                    epoch_id,
                    stream_id,
                    epoch_index,
                    stage1_artifact_hash,
                    stage2_artifact_hash,
                    changepoint_artifact_hash,
                    context_json,
                ),
            )
        return EpochRepository.get_epoch(db_path, epoch_id)

    @staticmethod
    def get_epoch(db_path: str, epoch_id: str) -> Optional[EpochRecord]:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM monitoring_epochs WHERE epoch_id = ?", (epoch_id,)
            ).fetchone()
            if row is None:
                return None
            return EpochRecord(
                epoch_id=row["epoch_id"],
                stream_id=row["stream_id"],
                epoch_index=row["epoch_index"],
                status=row["status"],
                termination_reason=row["termination_reason"],
                stage1_artifact_hash=row["stage1_artifact_hash"],
                stage2_artifact_hash=row["stage2_artifact_hash"],
                changepoint_artifact_hash=row["changepoint_artifact_hash"],
                calibration_context_json=row["calibration_context_json"],
                created_at=row["created_at"],
                closed_at=row["closed_at"],
            )
        finally:
            conn.close()

    @staticmethod
    def get_latest_epoch(db_path: str, stream_id: str) -> Optional[EpochRecord]:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM monitoring_epochs WHERE stream_id = ? ORDER BY epoch_index DESC LIMIT 1",
                (stream_id,),
            ).fetchone()
            if row is None:
                return None
            return EpochRecord(
                epoch_id=row["epoch_id"],
                stream_id=row["stream_id"],
                epoch_index=row["epoch_index"],
                status=row["status"],
                termination_reason=row["termination_reason"],
                stage1_artifact_hash=row["stage1_artifact_hash"],
                stage2_artifact_hash=row["stage2_artifact_hash"],
                changepoint_artifact_hash=row["changepoint_artifact_hash"],
                calibration_context_json=row["calibration_context_json"],
                created_at=row["created_at"],
                closed_at=row["closed_at"],
            )
        finally:
            conn.close()

    @staticmethod
    def update_epoch_status(
        db_path: str, epoch_id: str, status: str, termination_reason: Optional[str] = None
    ) -> None:
        with transaction_scope(db_path) as conn:
            conn.execute(
                """
                UPDATE monitoring_epochs 
                SET status = ?, termination_reason = ?, closed_at = CURRENT_TIMESTAMP
                WHERE epoch_id = ?
                """,
                (status, termination_reason, epoch_id),
            )


class SessionRepository:
    """Repository for append-only session ledger, detector snapshots, and threat assessments."""

    @staticmethod
    def get_session_by_id(db_path: str, epoch_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM monitoring_sessions WHERE epoch_id = ? AND session_id = ?",
                (epoch_id, session_id),
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    @staticmethod
    def get_latest_snapshot(db_path: str, epoch_id: str) -> Optional[Tuple[UnifiedMonitoringState, str]]:
        """
        Loads and cryptographically verifies the latest detector state snapshot for an epoch.
        Returns tuple of (UnifiedMonitoringState, snapshot_hash).
        """
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT * FROM detector_state_snapshots WHERE epoch_id = ? ORDER BY sequence_number DESC LIMIT 1",
                (epoch_id,),
            ).fetchone()
            if row is None:
                return None

            st2_dict = json.loads(row["stage2_state_json"])
            cp_dict = json.loads(row["changepoint_state_json"])
            payload = {
                "sequence_number": row["sequence_number"],
                "stage2_state": st2_dict,
                "changepoint_state": cp_dict,
            }
            recomputed_hash = compute_sha256_hash(payload)
            if recomputed_hash != row["snapshot_hash"]:
                raise CryptographicIntegrityError(
                    f"DB Tamper Alert! Snapshot for epoch {epoch_id} seq {row['sequence_number']} failed hash check."
                )

            unified_state = deserialize_unified_state(payload)
            return unified_state, row["snapshot_hash"]
        finally:
            conn.close()

    @staticmethod
    def get_threat_assessment(db_path: str, epoch_id: str, session_id: str) -> Optional[UnifiedThreatAssessment]:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT assessment_json FROM threat_assessments WHERE epoch_id = ? AND session_id = ?",
                (epoch_id, session_id),
            ).fetchone()
            if row is None:
                return None
            return deserialize_threat_assessment(json.loads(row["assessment_json"]))
        finally:
            conn.close()
