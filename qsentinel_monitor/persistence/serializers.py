"""
Phase 10 Canonical Serialization & Cryptographic Hashing for QSENTINEL.

Provides deterministic JSON serialization for all domain dataclasses, enums, tuples,
and floats, plus SHA-256 state hashing and integrity verification.
"""
import hashlib
import json
from dataclasses import is_dataclass, asdict
from enum import Enum
from typing import Any, Dict, Type, TypeVar, Optional, Tuple

from qsentinel_monitor.sequential_test_models import (
    SequentialTestState,
    Stage2DecisionStatus,
    Stage2ProvenanceIdentity,
)
from qsentinel_monitor.changepoint_models import (
    ChangePointTestState,
    ChangePointDecisionStatus,
    ChangePointProvenanceIdentity,
)
from qsentinel_monitor.threat_models import (
    SecurityPosture,
    ThreatSeverity,
    ProvenanceBundle,
    UnifiedThreatAssessment,
    UnifiedMonitoringState,
)


T = TypeVar("T")


def canonical_json_dumps(obj: Any) -> str:
    """
    Serializes a Python object or dataclass into a deterministic, canonical JSON string.
    Ensures sorted keys, exact enum string conversion, tuple-to-list conversion,
    and no whitespace drift.
    """
    def _encoder(item: Any) -> Any:
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, tuple):
            return list(item)
        if is_dataclass(item) and not isinstance(item, type):
            return asdict(item)
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    return json.dumps(obj, default=_encoder, sort_keys=True, separators=(",", ":"))


def compute_sha256_hash(payload: Any) -> str:
    """Computes a SHA-256 hex digest over a canonical JSON serialization of the payload."""
    canonical_str = canonical_json_dumps(payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


# --- De-serialization Helpers ---

def deserialize_stage2_provenance(d: Optional[Dict[str, Any]]) -> Optional[Stage2ProvenanceIdentity]:
    if d is None:
        return None
    return Stage2ProvenanceIdentity(
        artifact_content_hash=d["artifact_content_hash"],
        artifact_schema_version=d["artifact_schema_version"],
        architecture_version=d["architecture_version"],
        stage1_model_version=d["stage1_model_version"],
        stage2_model_version=d["stage2_model_version"],
    )


def deserialize_changepoint_provenance(d: Optional[Dict[str, Any]]) -> Optional[ChangePointProvenanceIdentity]:
    if d is None:
        return None
    return ChangePointProvenanceIdentity(
        artifact_content_hash=d["artifact_content_hash"],
        artifact_schema_version=d["artifact_schema_version"],
        architecture_version=d["architecture_version"],
        stage1_model_version=d["stage1_model_version"],
        changepoint_model_version=d["changepoint_model_version"],
    )


def deserialize_stage2_state(d: Dict[str, Any]) -> SequentialTestState:
    return SequentialTestState(
        cumulative_log_likelihood_ratio=float(d["cumulative_log_likelihood_ratio"]),
        processed_valid_count=int(d["processed_valid_count"]),
        skipped_session_count=int(d["skipped_session_count"]),
        last_accepted_session_id=d["last_accepted_session_id"],
        last_accepted_sequence_number=int(d["last_accepted_sequence_number"]),
        provenance_identity=deserialize_stage2_provenance(d.get("provenance_identity")),
        decision_status=Stage2DecisionStatus(d["decision_status"]),
        history_session_ids=tuple(d["history_session_ids"]),
    )


def deserialize_changepoint_state(d: Dict[str, Any]) -> ChangePointTestState:
    return ChangePointTestState(
        cusum_statistic=float(d["cusum_statistic"]),
        active_run_length=int(d["active_run_length"]),
        estimated_excursion_onset=d["estimated_excursion_onset"],
        processed_valid_count=int(d["processed_valid_count"]),
        skipped_session_count=int(d["skipped_session_count"]),
        last_accepted_session_id=d["last_accepted_session_id"],
        last_accepted_sequence_number=int(d["last_accepted_sequence_number"]),
        provenance_identity=deserialize_changepoint_provenance(d.get("provenance_identity")),
        decision_status=ChangePointDecisionStatus(d["decision_status"]),
        history_session_ids=tuple(d["history_session_ids"]),
    )


def deserialize_unified_state(d: Dict[str, Any]) -> UnifiedMonitoringState:
    return UnifiedMonitoringState(
        sequence_number=int(d["sequence_number"]),
        stage2_state=deserialize_stage2_state(d["stage2_state"]),
        changepoint_state=deserialize_changepoint_state(d["changepoint_state"]),
    )


def deserialize_threat_assessment(d: Dict[str, Any]) -> UnifiedThreatAssessment:
    prov = d["provenance_bundle"]
    prov_bundle = ProvenanceBundle(
        stage1_artifact_hash=prov["stage1_artifact_hash"],
        stage2_artifact_hash=prov["stage2_artifact_hash"],
        changepoint_artifact_hash=prov["changepoint_artifact_hash"],
        architecture_version=prov["architecture_version"],
    )
    return UnifiedThreatAssessment(
        session_id=d["session_id"],
        sequence_number=int(d["sequence_number"]),
        security_posture=SecurityPosture(d["security_posture"]),
        threat_severity=ThreatSeverity(d["threat_severity"]),
        contributing_detectors=tuple(d["contributing_detectors"]),
        explanation=d["explanation"],
        estimated_excursion_onset=d["estimated_excursion_onset"],
        stage2_horizon_exceeded=bool(d["stage2_horizon_exceeded"]),
        changepoint_horizon_exceeded=bool(d["changepoint_horizon_exceeded"]),
        provenance_bundle=prov_bundle,
    )
