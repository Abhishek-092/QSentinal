"""
Phase 8 Change-Point Calibration Loader & Artifact Unit Test Suite for QSENTINEL.

Verifies:
1. Canonical hashing reproducibility
2. Artifact loader schema validation
3. Cryptographic hash tampering detection
4. Calibration artifact generation & structure
"""
import json
import tempfile
import os
import pytest

from experiments.changepoint_calibration import (
    generate_changepoint_calibration_artifact,
    compute_changepoint_canonical_hash,
    save_changepoint_calibration_artifact,
)
from qsentinel_monitor.changepoint_calibration_loader import (
    load_changepoint_calibration_artifact,
    ChangePointCalibrationArtifact,
)


def test_canonical_hash_reproducibility():
    payload = {
        "schema_version": "1.0",
        "architecture_version": "v8.0",
        "changepoint_model_version": "v1.0",
        "calibration_configuration": {"alpha": 0.01},
        "seed_provenance": {"seed_start": 0},
        "calibration_table": [{"p": 0.0}],
    }
    h1 = compute_changepoint_canonical_hash(payload)
    h2 = compute_changepoint_canonical_hash(payload)
    assert h1 == h2
    assert len(h1) == 64


def test_artifact_generation_and_loading():
    payload = generate_changepoint_calibration_artifact(
        p_grid=[0.0, 0.05],
        n_qubits=200,
        alpha=0.01,
        horizon_sessions=5,
        n_trials_per_grid_point=10,
        seed_start=0,
    )
    assert "content_hash" in payload
    assert len(payload["calibration_table"]) == 2

    with tempfile.TemporaryDirectory() as tmpdir:
        art_path = os.path.join(tmpdir, "test_changepoint_artifact.json")
        save_changepoint_calibration_artifact(payload, art_path)

        loaded_artifact = load_changepoint_calibration_artifact(art_path)
        assert isinstance(loaded_artifact, ChangePointCalibrationArtifact)
        assert loaded_artifact.content_hash == payload["content_hash"]
        assert loaded_artifact.architecture_version == "v8.0"


def test_artifact_tamper_detection():
    payload = generate_changepoint_calibration_artifact(
        p_grid=[0.0, 0.05],
        n_qubits=200,
        alpha=0.01,
        horizon_sessions=5,
        n_trials_per_grid_point=10,
        seed_start=0,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        art_path = os.path.join(tmpdir, "tampered_artifact.json")
        # Tamper payload table after computing content_hash
        payload["calibration_table"][0]["null_offset_d"] = 999.99
        with open(art_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        with pytest.raises(ValueError, match="Cryptographic hash mismatch"):
            load_changepoint_calibration_artifact(art_path)
