"""
Fixed 3-qubit statevector representation for teleportation-distributed QS-L simulation.
Register layout:
- Index 0: Message qubit (|ψ⟩)
- Index 1: Sender's half of Bell pair (Alice)
- Index 2: Recipient's half of Bell pair (Bob)
"""
import numpy as np

# Basis state vectors (1D complex arrays)
KET_0 = np.array([1.0, 0.0], dtype=np.complex128)
KET_1 = np.array([0.0, 1.0], dtype=np.complex128)
KET_PLUS = (KET_0 + KET_1) / np.sqrt(2.0)
KET_MINUS = (KET_0 - KET_1) / np.sqrt(2.0)

# Single Qubit Gates
GATE_I = np.eye(2, dtype=np.complex128)
GATE_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
GATE_Y = np.array([[0.0, -1j], [1j, 0.0]], dtype=np.complex128)
GATE_Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
GATE_H = np.array([[1.0, 1.0], [1.0, -1.0]], dtype=np.complex128) / np.sqrt(2.0)


def tensor_product(*args: np.ndarray) -> np.ndarray:
    """Computes Kronecker tensor product across a sequence of statevectors or matrices."""
    res = args[0]
    for m in args[1:]:
        res = np.kron(res, m)
    return res


def prepare_bell_pair() -> np.ndarray:
    """
    Returns 2-qubit entangled Bell statevector |Φ+⟩.
    State dimension: 4.
    """
    bell_00 = tensor_product(KET_0, KET_0)
    bell_11 = tensor_product(KET_1, KET_1)
    return (bell_00 + bell_11) / np.sqrt(2.0)
