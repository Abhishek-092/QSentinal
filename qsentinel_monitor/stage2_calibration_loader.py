"""
Runtime-safe Stage 2 Calibration Artifact Loader for QSENTINEL (Phase 6D).

Loads and verifies versioned, content-hashed Stage 2 calibration artifacts from disk or dict.
PERFORMS NO MONTE CARLO SIMULATION, SEED ALLOCATION, OR RUNTIME CALIBRATION.
"""
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
import json
from experiments.stage2_calibration import compute_stage2_canonical_hash
from qsentinel_monitor.calibration_loader import ArtifactIntegrityError, ArtifactValidationError


@dataclass(frozen=True)
class Stage2CalibrationArtifact:
    schema_version: str
    architecture_version: str
    stage2_model_version: str
    calibration_configuration: Dict[str, Any]
    seed_provenance: Dict[str, Any]
    calibration_table: Tuple[Dict[str, Any], ...]
    content_hash: str


def load_stage2_calibration_artifact(json_data_or_path: Any) -> Stage2CalibrationArtifact:
    """
    Loads and verifies Stage 2 calibration artifact from a file path or dict.
    Verifies SHA-256 content hash against canonical payload re-serialization.
    Validates required horizon-bounded contract metadata.
    Returns immutable Stage2CalibrationArtifact frozen dataclass.
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
        raise ArtifactValidationError("Stage 2 artifact missing mandatory 'content_hash' field.")

    stored_hash = artifact_dict["content_hash"]
    canonical_payload = {k: v for k, v in artifact_dict.items() if k != "content_hash"}

    # Validate mandatory contract semantics
    calib_config = artifact_dict.get("calibration_configuration", {})
    if calib_config.get("calibration_guarantee") != "HORIZON_BOUNDED":
        raise ArtifactValidationError(
            f"Invalid Stage 2 calibration_guarantee: '{calib_config.get('calibration_guarantee')}'. Must be 'HORIZON_BOUNDED'."
        )
    if calib_config.get("calibrated_statistic") != "MAX_CUMULATIVE_EVIDENCE":
        raise ArtifactValidationError(
            f"Invalid Stage 2 calibrated_statistic: '{calib_config.get('calibrated_statistic')}'. Must be 'MAX_CUMULATIVE_EVIDENCE'."
        )

    recomputed_hash = compute_stage2_canonical_hash(canonical_payload)
    if recomputed_hash != stored_hash:
        raise ArtifactIntegrityError(
            f"Stage 2 artifact integrity hash mismatch! Stored: {stored_hash}, Recomputed: {recomputed_hash}"
        )

    return Stage2CalibrationArtifact(
        schema_version=artifact_dict["schema_version"],
        architecture_version=artifact_dict["architecture_version"],
        stage2_model_version=artifact_dict["stage2_model_version"],
        calibration_configuration=calib_config,
        seed_provenance=artifact_dict["seed_provenance"],
        calibration_table=tuple(artifact_dict["calibration_table"]),
        content_hash=stored_hash,
    )
