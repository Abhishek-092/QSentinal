"""3-qubit density-matrix operations.

Gates act as ρ ↦ UρU†. The depolarizing channel is the Kraus map
    E(ρ) = (1−p)ρ + (p/3)(XρX + YρY + ZρZ)
applied independently to each qubit — the laboratory average, not a
single stochastic jump.
"""

from __future__ import annotations

import numpy as np

from qds.pauli import I, X, Y, Z, cnot as cnot_ket, kron_n

DIM = 8


def as_rho(state: np.ndarray) -> np.ndarray:
    """Accept a ket or a density matrix and return a Hermitian ρ."""
    if state.ndim == 1:
        ket = state / np.linalg.norm(state)
        return np.outer(ket, np.conjugate(ket))
    rho = 0.5 * (state + state.conj().T)
    tr = float(np.real(np.trace(rho)))
    return rho / tr if tr > 0 else rho


def _unitary_single(qubit: int, op: np.ndarray, n_qubits: int = 3) -> np.ndarray:
    ops = [I] * n_qubits
    ops[qubit] = op
    return kron_n(*ops)


def apply_unitary(u: np.ndarray, rho: np.ndarray) -> np.ndarray:
    return u @ as_rho(rho) @ u.conj().T


def apply_single(qubit: int, op: np.ndarray, rho: np.ndarray, n_qubits: int = 3) -> np.ndarray:
    return apply_unitary(_unitary_single(qubit, op, n_qubits), rho)


def hadamard(qubit: int, rho: np.ndarray, n_qubits: int = 3) -> np.ndarray:
    h = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
    return apply_single(qubit, h, rho, n_qubits)


def ry(qubit: int, theta: float, rho: np.ndarray, n_qubits: int = 3) -> np.ndarray:
    c, s = np.cos(theta / 2.0), np.sin(theta / 2.0)
    mat = np.array([[c, -s], [s, c]], dtype=complex)
    return apply_single(qubit, mat, rho, n_qubits)


def cnot(control: int, target: int, rho: np.ndarray, n_qubits: int = 3) -> np.ndarray:
    u = np.zeros((2**n_qubits, 2**n_qubits), dtype=complex)
    for i in range(2**n_qubits):
        e = np.zeros(2**n_qubits, dtype=complex)
        e[i] = 1.0
        u[:, i] = cnot_ket(control, target, e, n_qubits)
    return apply_unitary(u, rho)


def _z_projector(qubit: int, bit: int, n_qubits: int = 3) -> np.ndarray:
    p = np.zeros((2**n_qubits, 2**n_qubits), dtype=complex)
    shift = n_qubits - 1 - qubit
    for i in range(2**n_qubits):
        if ((i >> shift) & 1) == bit:
            p[i, i] = 1.0
    return p


def measure_z(rho: np.ndarray, qubit: int, n_qubits: int = 3) -> tuple[int, np.ndarray]:
    """Projective Z measurement on a possibly mixed state."""
    rho = as_rho(rho)
    p0 = float(np.real(np.trace(_z_projector(qubit, 0, n_qubits) @ rho)))
    p0 = min(1.0, max(0.0, p0))
    outcome = 0 if np.random.random() < p0 else 1
    proj = _z_projector(qubit, outcome, n_qubits)
    collapsed = proj @ rho @ proj
    tr = float(np.real(np.trace(collapsed)))
    if tr > 1e-15:
        collapsed = collapsed / tr
    return outcome, collapsed


def depolarize_qubit(rho: np.ndarray, qubit: int, p: float, n_qubits: int = 3) -> np.ndarray:
    """Single-qubit depolarizing Kraus map."""
    rho = as_rho(rho)
    p = min(max(float(p), 0.0), 1.0)
    if p <= 0.0:
        return rho
    out = (1.0 - p) * rho
    for op in (X, Y, Z):
        u = _unitary_single(qubit, op, n_qubits)
        out = out + (p / 3.0) * (u @ rho @ u.conj().T)
    return out


def depolarizing_channel(state: np.ndarray, p: float, n_qubits: int = 3) -> np.ndarray:
    rho = as_rho(state)
    for q in range(n_qubits):
        rho = depolarize_qubit(rho, q, p, n_qubits)
    return rho


def pauli_z(qubit: int, n_qubits: int = 3) -> np.ndarray:
    return _unitary_single(qubit, Z, n_qubits)
