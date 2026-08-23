"""
Runtime-safe Sequential Calibration Artifact Loader for QSENTINEL (Phase 6C).

Loads and verifies versioned, content-hashed sequential calibration artifacts from disk.
PERFORMS NO MONTE CARLO SIMULATION, SEED ALLOCATION, OR RUNTIME CALIBRATION.
"""
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
import json
import hashlib


class SequentialArtifactIntegrityError(ValueError):
    """Raised when a sequential calibration artifact fails SHA-256 content hash verification."""
    pass


class SequentialArtifactValidationError(ValueError):
    """Raised when a sequential calibration artifact structure or schema is invalid."""
    pass


@dataclass(frozen=True)
class SequentialCalibrationArtifact:
    schema_version: str
    architecture_version: str
    stage1_model_version: str
    sequential_model_version: str
    stage1_calibration_provenance: Dict[str, Any]
    sequential_configuration: Dict[str, Any]
    seed_provenance: Dict[str, Any]
    empirical_sequential_threshold: float
    calibration_summary: Dict[str, Any]
    content_hash: str


def compute_sequential_canonical_hash(canonical_payload: Dict[str, Any]) -> str:
    """
    Computes SHA-256 content hash from canonical JSON string (sorted keys, indent 2, ascii).
    """
    json_str = json.dumps(canonical_payload, sort_keys=True, indent=2, ensure_ascii=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def load_sequential_calibration_artifact(json_data_or_path: Any) -> SequentialCalibrationArtifact:
    """
    Loads and verifies sequential calibration artifact from a file path or dict.
    Verifies SHA-256 content hash against canonical payload re-serialization.
    Returns immutable SequentialCalibrationArtifact frozen dataclass.
    Executes ZERO simulation trials or seed allocation.
    """
    if isinstance(json_data_or_path, str):
        with open(json_data_or_path, "r", encoding="utf-8") as f:
            artifact_dict = json.load(f)
    elif isinstance(json_data_or_path, dict):
        artifact_dict = json_data_or_path
    else:
        raise SequentialArtifactValidationError(f"Unsupported artifact input type: {type(json_data_or_path)}")

    if "content_hash" not in artifact_dict:
        raise SequentialArtifactValidationError("Artifact missing mandatory 'content_hash' field.")

    stored_hash = artifact_dict["content_hash"]
    canonical_payload = {k: v for k, v in artifact_dict.items() if k != "content_hash"}

    recomputed_hash = compute_sequential_canonical_hash(canonical_payload)
    if recomputed_hash != stored_hash:
        raise SequentialArtifactIntegrityError(
            f"Sequential artifact integrity hash mismatch! Stored: {stored_hash}, Recomputed: {recomputed_hash}"
        )

    return SequentialCalibrationArtifact(
        schema_version=artifact_dict["schema_version"],
        architecture_version=artifact_dict["architecture_version"],
        stage1_model_version=artifact_dict["stage1_model_version"],
        sequential_model_version=artifact_dict["sequential_model_version"],
        stage1_calibration_provenance=artifact_dict["stage1_calibration_provenance"],
        sequential_configuration=artifact_dict["sequential_configuration"],
        seed_provenance=artifact_dict["seed_provenance"],
        empirical_sequential_threshold=float(artifact_dict["empirical_sequential_threshold"]),
        calibration_summary=artifact_dict["calibration_summary"],
        content_hash=stored_hash,
    )
