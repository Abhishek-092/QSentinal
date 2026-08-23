"""
Pauli eigenstate key encoding and correction logic for quantum teleportation.
"""
import numpy as np
from qds.bell_pair import KET_0, KET_1, KET_PLUS, KET_MINUS, GATE_I, GATE_X, GATE_Z


def encode_eigenstate(bit: int, basis: int) -> np.ndarray:
    """
    Encodes key bit k_i in basis b_i:
    - basis 0 (Z-basis): bit 0 -> |0⟩, bit 1 -> |1⟩
    - basis 1 (X-basis): bit 0 -> |+⟩, bit 1 -> |-⟩
    """
    if basis == 0:
        return KET_0.copy() if bit == 0 else KET_1.copy()
    elif basis == 1:
        return KET_PLUS.copy() if bit == 0 else KET_MINUS.copy()
    else:
        raise ValueError(f"Invalid basis {basis}. Must be 0 (Z) or 1 (X).")


def correct_pauli(state: np.ndarray, b1: int, b2: int) -> np.ndarray:
    """
    Applies Pauli correction matrix on 1-qubit Bob state given Alice's Bell measurement bits (b1, b2):
    - 00: I
    - 01: X
    - 10: Z
    - 11: XZ (Z then X)
    """
    corrected = state.copy()
    if b2 == 1:
        corrected = GATE_X @ corrected
    if b1 == 1:
        corrected = GATE_Z @ corrected
    return corrected
