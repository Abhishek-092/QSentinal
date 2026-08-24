"""
Phase 10 Persistence Configuration & SQLite Database Engine for QSENTINEL.

Provides SQLite connection management with WAL (Write-Ahead Logging), foreign key constraints,
schema migrations, and explicit transactional boundaries.
"""
import sqlite3
import os
from contextlib import contextmanager
from typing import Generator


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- 1. Immutable Content-Addressed Calibration Artifact Store
CREATE TABLE IF NOT EXISTS calibration_artifacts (
    content_hash TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    architecture_version TEXT NOT NULL,
    artifact_type TEXT NOT NULL, -- 'STAGE1', 'STAGE2', 'CHANGEPOINT'
    json_payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Monitoring Streams
CREATE TABLE IF NOT EXISTS monitoring_streams (
    stream_id TEXT PRIMARY KEY,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'ACTIVE' -- 'ACTIVE', 'ARCHIVED'
);

-- 3. Monitoring Epochs
CREATE TABLE IF NOT EXISTS monitoring_epochs (
    epoch_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL,
    epoch_index INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'ELEVATED', 'EXPIRED', 'CLOSED'
    termination_reason TEXT,
    stage1_artifact_hash TEXT,
    stage2_artifact_hash TEXT,
    changepoint_artifact_hash TEXT,
    calibration_context_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    FOREIGN KEY (stream_id) REFERENCES monitoring_streams(stream_id),
    FOREIGN KEY (stage1_artifact_hash) REFERENCES calibration_artifacts(content_hash),
    FOREIGN KEY (stage2_artifact_hash) REFERENCES calibration_artifacts(content_hash),
    FOREIGN KEY (changepoint_artifact_hash) REFERENCES calibration_artifacts(content_hash),
    UNIQUE(stream_id, epoch_index)
);

-- 4. Append-Only Session Ledger
CREATE TABLE IF NOT EXISTS monitoring_sessions (
    session_id TEXT NOT NULL,
    epoch_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    transcript_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (epoch_id, session_id),
    FOREIGN KEY (epoch_id) REFERENCES monitoring_epochs(epoch_id),
    UNIQUE(epoch_id, sequence_number)
);

-- 5. Detector State Snapshots
CREATE TABLE IF NOT EXISTS detector_state_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    epoch_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    stage2_state_json TEXT NOT NULL,
    changepoint_state_json TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (epoch_id) REFERENCES monitoring_epochs(epoch_id),
    UNIQUE(epoch_id, sequence_number)
);

-- 6. Historical Threat Assessments
CREATE TABLE IF NOT EXISTS threat_assessments (
    assessment_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    epoch_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    security_posture TEXT NOT NULL,
    threat_severity TEXT NOT NULL,
    assessment_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (epoch_id) REFERENCES monitoring_epochs(epoch_id),
    FOREIGN KEY (epoch_id, session_id) REFERENCES monitoring_sessions(epoch_id, session_id)
);
"""


def init_database(db_path: str) -> None:
    """Initializes SQLite database file with WAL mode, foreign keys, and full schema."""
    parent_dir = os.path.dirname(db_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def get_connection(db_path: str) -> sqlite3.Connection:
    """Returns a configured SQLite connection."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction_scope(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing an atomic SQLite write transaction."""
    conn = get_connection(db_path)
    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
