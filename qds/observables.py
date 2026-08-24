"""Physical observables on a 3-qubit statevector.

Qubit order is |q0 q1 q2⟩ with q0 = message, q1 = sender EPR, q2 = recipient EPR.
"""

from __future__ import annotations

import numpy as np

from qds.density import as_rho, pauli_z
from qds.pauli import X, Y, Z

KETS = [format(i, "03b") for i in range(8)]


def _normalize(state: np.ndarray) -> np.ndarray:
    nrm = np.linalg.norm(state)
    return state / nrm if nrm > 0 else state


def reduced_qubit(state: np.ndarray, qubit: int, n_qubits: int = 3) -> np.ndarray:
    """Partial trace → 2×2 density matrix of one qubit (ket or ρ)."""
    if state.ndim == 2:
        rho = as_rho(state)
        rho_q = np.zeros((2, 2), dtype=complex)
        shift = n_qubits - 1 - qubit
        dim = 2**n_qubits
        for i in range(dim):
            bi = (i >> shift) & 1
            rest_i = i ^ (bi << shift)
            for j in range(dim):
                bj = (j >> shift) & 1
                rest_j = j ^ (bj << shift)
                if rest_i == rest_j:
                    rho_q[bi, bj] += rho[i, j]
        return rho_q
    state = _normalize(state)
    rho = np.zeros((2, 2), dtype=complex)
    shift = n_qubits - 1 - qubit
    for i, ai in enumerate(state):
        bi = (i >> shift) & 1
        rest_i = i ^ (bi << shift)
        for j, aj in enumerate(state):
            bj = (j >> shift) & 1
            rest_j = j ^ (bj << shift)
            if rest_i == rest_j:
                rho[bi, bj] += ai * np.conjugate(aj)
    return rho


def bloch_vector(state: np.ndarray, qubit: int) -> dict[str, float]:
    rho = reduced_qubit(state, qubit)
    return {
        "x": float(np.real(np.trace(rho @ X))),
        "y": float(np.real(np.trace(rho @ Y))),
        "z": float(np.real(np.trace(rho @ Z))),
    }


def expectation_zz(state: np.ndarray, q_a: int, q_b: int, n_qubits: int = 3) -> float:
    """⟨Z⊗Z⟩ on two qubits. For |Φ+⟩ this equals +1."""
    if state.ndim == 2:
        rho = as_rho(state)
        zz = pauli_z(q_a, n_qubits) @ pauli_z(q_b, n_qubits)
        return float(np.real(np.trace(rho @ zz)))
    exp = 0.0
    sa = n_qubits - 1 - q_a
    sb = n_qubits - 1 - q_b
    for i, amp in enumerate(state):
        p = abs(amp) ** 2
        za = 1.0 if ((i >> sa) & 1) == 0 else -1.0
        zb = 1.0 if ((i >> sb) & 1) == 0 else -1.0
        exp += p * za * zb
    return float(exp)


def von_neumann_entropy(rho: np.ndarray) -> float:
    """S(ρ) = −Tr(ρ log₂ ρ) in bits."""
    eig = np.clip(np.real(np.linalg.eigvalsh(rho)), 0.0, 1.0)
    eig = eig[eig > 1e-12]
    if eig.size == 0:
        return 0.0
    return float(-np.sum(eig * np.log2(eig)))


def message_ket(theta: float) -> np.ndarray:
    return np.array([np.cos(theta / 2.0), np.sin(theta / 2.0)], dtype=complex)


def fidelity_pure(rho: np.ndarray, ket: np.ndarray) -> float:
    """F = ⟨ψ|ρ|ψ⟩ for a pure target against a (possibly mixed) qubit."""
    ket = ket / np.linalg.norm(ket)
    return float(np.real(np.conjugate(ket) @ rho @ ket))


def amplitudes(state: np.ndarray) -> list[dict]:
    if state.ndim == 2:
        rho = as_rho(state)
        evals, evecs = np.linalg.eigh(rho)
        psi = evecs[:, int(np.argmax(evals))]
        rows = []
        for i in range(rho.shape[0]):
            label = f"|{KETS[i]}⟩"
            rows.append({
                "ket": label,
                "re": round(float(np.real(psi[i])), 6),
                "im": round(float(np.imag(psi[i])), 6),
                "p": round(float(np.real(rho[i, i])), 6),
            })
        return rows
    state = _normalize(state)
    rows = []
    for i, amp in enumerate(state):
        label = f"|{KETS[i]}⟩"
        rows.append({
            "ket": label,
            "re": round(float(np.real(amp)), 6),
            "im": round(float(np.imag(amp)), 6),
            "p": round(float(abs(amp) ** 2), 6),
        })
    return rows


def snapshot(state: np.ndarray, theta: float, note: str = "") -> dict:
    """JSON-safe laboratory readout of the live quantum state."""
    if state.ndim == 1:
        state = _normalize(state)
    rho_b = reduced_qubit(state, 2)
    ket = message_ket(theta)
    fid = fidelity_pure(rho_b, ket)
    bloch_b = bloch_vector(state, 2)
    bloch_m = {
        "x": float(np.real(np.conjugate(ket) @ X @ ket)),
        "y": float(np.real(np.conjugate(ket) @ Y @ ket)),
        "z": float(np.real(np.conjugate(ket) @ Z @ ket)),
    }
    entropy = von_neumann_entropy(rho_b)
    bell_zz = expectation_zz(state, 1, 2)
    infidelity = max(0.0, 1.0 - fid)
    return {
        "note": note,
        "amplitudes": amplitudes(state),
        "bloch_bob": bloch_b,
        "bloch_message": bloch_m,
        "fidelity": fid,
        "mismatch_rate": infidelity,
        "correlation": bell_zz,
        "entropy": entropy,
        "pauli_consistency": max(0.0, min(1.0, 0.5 * (1.0 + float(np.dot(
            [bloch_b["x"], bloch_b["y"], bloch_b["z"]],
            [bloch_m["x"], bloch_m["y"], bloch_m["z"]],
        ))))),
        "theta": float(theta),
    }
