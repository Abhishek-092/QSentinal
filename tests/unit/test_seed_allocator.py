import pytest
from experiments.seed_allocator import SeedAllocator, SeedAllocationError, SEED_RANGES

def test_seed_ranges_non_overlapping():
    """Verify that CALIBRATION, VALIDATION, and EVALUATION ranges share zero overlap."""
    ranges = list(SEED_RANGES.values())
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            s1, e1 = ranges[i]
            s2, e2 = ranges[j]
            assert e1 <= s2 or e2 <= s1, f"Overlap detected between range {ranges[i]} and {ranges[j]}"

def test_seed_allocator_valid():
    """Verify correct seed allocation within range bounds."""
    seed = SeedAllocator.get_seed("CALIBRATION", 100)
    assert seed == 100
    assert SeedAllocator.validate_seed("CALIBRATION", seed) is True

    eval_seed = SeedAllocator.get_seed("EVALUATION", 500)
    assert eval_seed == 100_500
    assert SeedAllocator.validate_seed("EVALUATION", eval_seed) is True

def test_seed_allocator_out_of_bounds_raises():
    """Verify that requesting seeds outside purpose boundaries raises SeedAllocationError."""
    with pytest.raises(SeedAllocationError):
        SeedAllocator.get_seed("CALIBRATION", 60_000)

    with pytest.raises(SeedAllocationError):
        SeedAllocator.validate_seed("CALIBRATION", 75_000)
