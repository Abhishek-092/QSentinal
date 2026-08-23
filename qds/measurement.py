"""
Projective measurement module for recipient state verification in random BB84 basis.
"""
import numpy as np
from qds.bell_pair import KET_0, KET_1, KET_PLUS, KET_MINUS


def project_measurement(state: np.ndarray, basis: int, rng: np.random.Generator = None) -> int:
    """
    Projectively measures 1-qubit state in specified basis:
    - basis 0 (Z-basis): projects onto {|0⟩, |1⟩}
    - basis 1 (X-basis): projects onto {|+⟩, |-⟩}
    Returns outcome bit: 0 or 1.
    """
    if rng is None:
        rng = np.random.default_rng()

    if basis == 0:
        p0 = np.abs(np.vdot(KET_0, state)) ** 2
    elif basis == 1:
        p0 = np.abs(np.vdot(KET_PLUS, state)) ** 2
    else:
        raise ValueError(f"Invalid measurement basis {basis}. Must be 0 or 1.")

    p0 = np.clip(p0, 0.0, 1.0)
    return 0 if rng.random() < p0 else 1
