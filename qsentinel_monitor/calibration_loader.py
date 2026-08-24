"""
Runtime-safe Calibration Artifact Loader for QSENTINEL.

Loads and verifies versioned, content-hashed calibration artifacts from disk.
PERFORMS NO MONTE CARLO SIMULATION, SEED ALLOCATION, OR RUNTIME CALIBRATION.
"""
from dataclasses import dataclass
from typing import Any
import json
from experiments.calibration import compute_canonical_hash


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact fails SHA-256 content hash verification."""
    pass


class ArtifactValidationError(ValueError):
    """Raised when an artifact structure or schema is invalid."""
    pass


@dataclass(frozen=True)
class CalibrationArtifact:
    schema_version: str
    architecture_version: str
    stage1_model_version: str
    calibration_configuration: dict[str, Any]
    seed_provenance: dict[str, Any]
    calibration_table: tuple[dict[str, Any], ...]
    content_hash: str


def load_calibration_artifact(json_data_or_path: Any) -> CalibrationArtifact:
    """
    Loads and verifies calibration artifact from a file path or dict.
    Verifies SHA-256 content hash against canonical payload re-serialization.
    Returns immutable CalibrationArtifact frozen dataclass.
    Executes ZERO simulation trials or seed allocation.
    """
    if isinstance(json_data_or_path, str):
        with open(json_data_or_path, "r", encoding="utf-8") as f:
            artifact_dict = json.load(f)
    elif isinstance(json_data_or_path, dict):
        artifact_dict = json_data_or_path
    else:
        raise ArtifactValidationError(f"Unsupported artifact input type: {type(json_data_or_path)}")

    if "content_hash" not in artifact_dict:
        raise ArtifactValidationError("Artifact missing mandatory 'content_hash' field.")

    stored_hash = artifact_dict["content_hash"]
    canonical_payload = {k: v for k, v in artifact_dict.items() if k != "content_hash"}

    recomputed_hash = compute_canonical_hash(canonical_payload)
    if recomputed_hash != stored_hash:
        raise ArtifactIntegrityError(
            f"Artifact integrity hash mismatch! Stored: {stored_hash}, Recomputed: {recomputed_hash}"
        )

    return CalibrationArtifact(
        schema_version=artifact_dict["schema_version"],
        architecture_version=artifact_dict["architecture_version"],
        stage1_model_version=artifact_dict["stage1_model_version"],
        calibration_configuration=artifact_dict["calibration_configuration"],
        seed_provenance=artifact_dict["seed_provenance"],
        calibration_table=tuple(artifact_dict["calibration_table"]),
        content_hash=stored_hash,
    )
