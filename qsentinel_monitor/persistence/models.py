"""
Phase 10 Persistence DTOs & Custom Integrity Exceptions for QSENTINEL.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


class CryptographicIntegrityError(Exception):
    """Raised when an artifact or snapshot hash check fails on load/restore."""
    pass


class ProvenanceMismatchError(Exception):
    """Raised when restored detector provenance does not match bound epoch artifacts."""
    pass


class DuplicateSessionError(Exception):
    """Raised when a session sequence or ID is duplicated in an epoch."""
    pass


class ConflictingSessionIdError(Exception):
    """Raised when a session ID is reused with conflicting fingerprint/transcript content."""
    pass


class EpochClosedError(Exception):
    """Raised when attempting to submit a session to a closed or terminal epoch."""
    pass


@dataclass(frozen=True)
class StreamRecord:
    stream_id: str
    description: str
    created_at: str
    status: str


@dataclass(frozen=True)
class EpochRecord:
    epoch_id: str
    stream_id: str
    epoch_index: int
    status: str
    termination_reason: Optional[str]
    stage1_artifact_hash: Optional[str]
    stage2_artifact_hash: Optional[str]
    changepoint_artifact_hash: Optional[str]
    calibration_context_json: str
    created_at: str
    closed_at: Optional[str]
