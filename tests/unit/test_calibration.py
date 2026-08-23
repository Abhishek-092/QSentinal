import pytest
json_import = pytest.importorskip("json")
from qds.protocol import SessionConfig
from experiments.seed_allocator import SeedAllocator, SeedAllocationError
from experiments.calibration import generate_calibration_artifact, compute_canonical_hash
from qsentinel_monitor.calibration_loader import (
    load_calibration_artifact,
    ArtifactIntegrityError,
    ArtifactValidationError,
    CalibrationArtifact,
)


def test_seed_separation_enforcement():
    """Verify that calibration runner rejects overflow seeds or inappropriate purpose queries."""
    with pytest.raises(SeedAllocationError):
        # 60000 trials exceeds max CALIBRATION range limit (50,000)
        generate_calibration_artifact(n_trials_per_grid_point=10000, p_grid=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5])

    # Direct SeedAllocator checks for offset overflow
    with pytest.raises(SeedAllocationError):
        SeedAllocator.get_seed("CALIBRATION", 60_000)

    # Validate that CALIBRATION seed cannot be validated as a VALIDATION or EVALUATION seed
    calib_seed = SeedAllocator.get_seed("CALIBRATION", 10)
    with pytest.raises(SeedAllocationError):
        SeedAllocator.validate_seed("VALIDATION", calib_seed)

    with pytest.raises(SeedAllocationError):
        SeedAllocator.validate_seed("EVALUATION", calib_seed)


def test_calibration_reproducibility_and_hashing():
    """Verify identical inputs produce 100% identical canonical payloads and SHA-256 content hashes."""
    art1 = generate_calibration_artifact(n_trials_per_grid_point=20, p_grid=[0.0, 0.1])
    art2 = generate_calibration_artifact(n_trials_per_grid_point=20, p_grid=[0.0, 0.1])

    assert art1["content_hash"] == art2["content_hash"]
    assert art1 == art2


def test_different_config_alters_provenance_and_hash():
    """Verify that changing calibration config produces different provenance and content hash."""
    art1 = generate_calibration_artifact(n_trials_per_grid_point=20, p_grid=[0.0, 0.1])
    art2 = generate_calibration_artifact(n_trials_per_grid_point=30, p_grid=[0.0, 0.1])

    assert art1["content_hash"] != art2["content_hash"]


def test_p0_boundary_degeneracy_handling():
    """
    MANDATORY BOUNDARY TEST:
    Verify p = 0.0 boundary null classification:
    - null_classification == "DEGENERATE_BOUNDARY_NULL"
    - empirical_critical_value == 0.0
    - asymptotic_reference_applicability == "NOT_REGULARLY_APPLICABLE"
    - asymptotic_critical_value is None
    """
    art = generate_calibration_artifact(n_trials_per_grid_point=20, p_grid=[0.0, 0.1])

    entry_p0 = next(e for e in art["calibration_table"] if e["p"] == 0.0)
    assert entry_p0["null_classification"] == "DEGENERATE_BOUNDARY_NULL"
    assert entry_p0["empirical_critical_value"] == 0.0
    assert entry_p0["asymptotic_reference_applicability"] == "NOT_REGULARLY_APPLICABLE"
    assert entry_p0["asymptotic_critical_value"] is None

    entry_p1 = next(e for e in art["calibration_table"] if e["p"] == 0.1)
    assert entry_p1["null_classification"] == "REGULAR_INTERIOR_NULL"
    assert entry_p1["asymptotic_reference_applicability"] == "REGULAR_CHI2_DF1"
    assert entry_p1["asymptotic_critical_value"] is not None


def test_artifact_tampering_detection():
    """Verify modifying any character in artifact JSON triggers ArtifactIntegrityError on load."""
    art = generate_calibration_artifact(n_trials_per_grid_point=20, p_grid=[0.0, 0.1])

    # Tamper with empirical critical value in table
    import json
    art_tampered = json.loads(json.dumps(art))
    art_tampered["calibration_table"][1]["empirical_critical_value"] += 99.9

    with pytest.raises(ArtifactIntegrityError):
        load_calibration_artifact(art_tampered)


def test_runtime_loader_zero_calibration_work():
    """Verify runtime artifact loader loads verified CalibrationArtifact without performing calibration."""
    art = generate_calibration_artifact(n_trials_per_grid_point=20, p_grid=[0.0, 0.1])
    loaded_art = load_calibration_artifact(art)

    assert isinstance(loaded_art, CalibrationArtifact)
    assert loaded_art.content_hash == art["content_hash"]
    assert isinstance(loaded_art.calibration_table, tuple)
