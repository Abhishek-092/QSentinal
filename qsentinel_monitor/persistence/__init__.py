"""
Persistence Package Initialization.
"""
from qsentinel_monitor.persistence.database import init_database, get_connection, transaction_scope
from qsentinel_monitor.persistence.models import (
    CryptographicIntegrityError,
    ProvenanceMismatchError,
    DuplicateSessionError,
    ConflictingSessionIdError,
    EpochClosedError,
    StreamRecord,
    EpochRecord,
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

__all__ = [
    "init_database",
    "get_connection",
    "transaction_scope",
    "CryptographicIntegrityError",
    "ProvenanceMismatchError",
    "DuplicateSessionError",
    "ConflictingSessionIdError",
    "EpochClosedError",
    "StreamRecord",
    "EpochRecord",
    "canonical_json_dumps",
    "compute_sha256_hash",
    "deserialize_unified_state",
    "deserialize_threat_assessment",
    "ArtifactRepository",
    "StreamRepository",
    "EpochRepository",
    "SessionRepository",
]
