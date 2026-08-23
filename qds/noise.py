"""
Quantum noise channel model.
Injects symmetric depolarizing noise with error parameter p:
E(ρ) = (1 - p) ρ + (p / 3) (X ρ X + Y ρ Y + Z ρ Z)
"""
import numpy as np
from qds.bell_pair import GATE_I, GATE_X, GATE_Y, GATE_Z


def depolarize(state: np.ndarray, p: float, rng: np.random.Generator = None) -> np.ndarray:
    """
    Applies symmetric depolarizing channel with parameter p ∈ [0, 0.5] on a 1-qubit statevector.
    With prob (1 - p): state unchanged (Identity)
    With prob p/3: apply X
    With prob p/3: apply Y
    With prob p/3: apply Z
    """
    if p <= 0.0:
        return state.copy()

    if rng is None:
        rng = np.random.default_rng()

    p_no_error = 1.0 - p
    p_x = p / 3.0
    p_y = p / 3.0
    p_z = p / 3.0

    r = rng.random()
    if r < p_no_error:
        return state.copy()
    elif r < p_no_error + p_x:
        return GATE_X @ state
    elif r < p_no_error + p_x + p_y:
        return GATE_Y @ state
    else:
        return GATE_Z @ state
