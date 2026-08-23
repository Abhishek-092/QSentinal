"""
SeedAllocator for QSENTINEL.

Enforces non-overlapping, runtime-checked seed ranges for:
- CALIBRATION:  [0, 50_000)
- VALIDATION:   [50_000, 100_000)
- EVALUATION:   [100_000, 1_000_000)

Any attempt to request a seed outside the declared range for a given purpose raises SeedAllocationError.
"""
from typing import Literal

PurposeType = Literal["CALIBRATION", "VALIDATION", "EVALUATION"]

SEED_RANGES = {
    "CALIBRATION": (0, 50_000),
    "VALIDATION": (50_000, 100_000),
    "EVALUATION": (100_000, 1_000_000),
}


class SeedAllocationError(ValueError):
    """Raised when a seed or range violates declared allocation boundaries."""
    pass


class SeedAllocator:
    @staticmethod
    def get_seed(purpose: PurposeType, offset: int) -> int:
        """
        Returns a single deterministic seed given a purpose and trial offset.
        """
        if purpose not in SEED_RANGES:
            raise SeedAllocationError(f"Unknown purpose '{purpose}'. Must be one of {list(SEED_RANGES.keys())}")
        
        start, end = SEED_RANGES[purpose]
        seed = start + offset
        if seed >= end:
            raise SeedAllocationError(
                f"Offset {offset} for purpose '{purpose}' exceeds max range boundary [{start}, {end})."
            )
        return seed

    @staticmethod
    def validate_seed(purpose: PurposeType, seed: int) -> bool:
        """
        Validates whether a given seed falls strictly within the declared purpose range.
        """
        if purpose not in SEED_RANGES:
            raise SeedAllocationError(f"Unknown purpose '{purpose}'")
        start, end = SEED_RANGES[purpose]
        if not (start <= seed < end):
            raise SeedAllocationError(
                f"Seed {seed} is outside the allowed range [{start}, {end}) for purpose '{purpose}'."
            )
        return True
