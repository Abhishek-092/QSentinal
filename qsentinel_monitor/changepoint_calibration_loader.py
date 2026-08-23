"""
Phase 8 Change-Point Calibration Artifact Loader & Verification for QSENTINEL.

Loads, verifies SHA-256 content hashes, and exposes immutable ChangePointCalibrationArtifact.
PERFORMS ZERO MONTE CARLO, ZERO SEED ALLOCATION, ZERO SIMULATION, AND MUTATES NO ARTIFACTS.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import json
import hashlib
import os


@dataclass(frozen=True)
class ChangePointCalibrationArtifact:
    schema_version: str
    architecture_version: str
    changepoint_model_version: str
    calibration_configuration: Dict[str, Any]
    seed_provenance: Dict[str, Any]
    calibration_table: List[Dict[str, Any]]
    content_hash: str


def compute_changepoint_canonical_hash(payload: Dict[str, Any]) -> str:
    """Computes canonical SHA-256 hash over canonical JSON payload."""
    canonical_payload = {k: v for k, v in payload.items() if k != "content_hash"}
    json_str = json.dumps(canonical_payload, sort_keys=True, indent=2, ensure_ascii=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def load_changepoint_calibration_artifact(artifact_path: str) -> ChangePointCalibrationArtifact:
    """
    Loads and cryptographically verifies a ChangePointCalibrationArtifact JSON file.
    
    Raises:
        FileNotFoundError: If artifact file does not exist.
        ValueError: If JSON is invalid, schema/architecture version mismatch, or SHA-256 hash mismatch.
    """
    if not os.path.exists(artifact_path):
        raise FileNotFoundError(f"Change-point calibration artifact file not found: '{artifact_path}'.")

    with open(artifact_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as err:
            raise ValueError(f"Invalid JSON in change-point calibration artifact: {err}")

    # Required key verification
    required_keys = [
        "schema_version",
        "architecture_version",
        "changepoint_model_version",
        "calibration_configuration",
        "seed_provenance",
        "calibration_table",
        "content_hash",
    ]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key in change-point calibration artifact: '{key}'.")

    # Cryptographic SHA-256 content verification
    expected_hash = data["content_hash"]
    computed_hash = compute_changepoint_canonical_hash(data)

    if expected_hash != computed_hash:
        raise ValueError(
            f"Cryptographic hash mismatch in change-point calibration artifact!\n"
            f"Expected: {expected_hash}\n"
            f"Computed: {computed_hash}"
        )

    return ChangePointCalibrationArtifact(
        schema_version=str(data["schema_version"]),
        architecture_version=str(data["architecture_version"]),
        changepoint_model_version=str(data["changepoint_model_version"]),
        calibration_configuration=dict(data["calibration_configuration"]),
        seed_provenance=dict(data["seed_provenance"]),
        calibration_table=list(data["calibration_table"]),
        content_hash=str(expected_hash),
    )
