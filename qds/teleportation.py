"""
3-Qubit quantum teleportation execution module.
State register: |ψ⟩_message ⊗ |Φ+⟩_bell (3 qubits total, dimension 8)
"""

import numpy as np
from qds.bell_pair import prepare_bell_pair, tensor_product, KET_0, KET_1, GATE_H
from qds.pauli import correct_pauli


def apply_physical_attack(
    psi_3q: np.ndarray,
    attack: str | None,
    rng: np.random.Generator,
) -> np.ndarray:
    """Applies physical 3-qubit state evolution for physical attacks prior to Bell measurement."""
    if not attack:
        return psi_3q

    if attack in ("intercept_resend", "channel_manipulation_intercept"):
        # Attacker intercepts Alice's EPR qubit (qubit 1) and measures in Z basis
        p0 = sum(abs(psi_3q[i]) ** 2 for i in range(8) if ((i >> 1) & 1) == 0)
        p0 = min(1.0, max(0.0, float(p0)))
        outcome = 0 if rng.random() < p0 else 1
        collapsed = psi_3q.copy()
        for i in range(8):
            if ((i >> 1) & 1) != outcome:
                collapsed[i] = 0.0
        nrm = np.linalg.norm(collapsed)
        return collapsed / nrm if nrm > 0 else psi_3q

    elif attack in ("basis_spoof", "x_basis_intercept"):
        # Attacker intercepts qubit 1 in X basis: H1 -> Z-meas -> H1
        h_1 = tensor_product(np.eye(2, dtype=np.complex128), GATE_H, np.eye(2, dtype=np.complex128))
        rotated = h_1 @ psi_3q
        p0 = sum(abs(rotated[i]) ** 2 for i in range(8) if ((i >> 1) & 1) == 0)
        p0 = min(1.0, max(0.0, float(p0)))
        outcome = 0 if rng.random() < p0 else 1
        collapsed = rotated.copy()
        for i in range(8):
            if ((i >> 1) & 1) != outcome:
                collapsed[i] = 0.0
        nrm = np.linalg.norm(collapsed)
        if nrm > 0:
            collapsed /= nrm
        return h_1 @ collapsed

    elif attack in ("entanglement_probe", "probe"):
        # Extra CNOT interaction: control = Bob's qubit 2, target = Alice's EPR qubit 1
        cnot_probe = np.zeros((8, 8), dtype=np.complex128)
        for i in range(8):
            q0 = (i >> 2) & 1
            q1 = (i >> 1) & 1
            q2 = i & 1
            if q2 == 1:
                target_i = (q0 << 2) | ((1 - q1) << 1) | q2
                cnot_probe[target_i, i] = 1.0
            else:
                cnot_probe[i, i] = 1.0
        return cnot_probe @ psi_3q

    return psi_3q


def teleport(
    message_state: np.ndarray,
    rng: np.random.Generator = None,
    apply_correction: bool = True,
    attack: str | None = None,
) -> tuple[tuple[int, int], np.ndarray]:
    """
    Executes quantum teleportation of message_state (1 qubit) using a Bell pair.
    Returns:
        ((b1, b2), teleported_bob_state)
    where (b1, b2) are sender's 2-bit Bell measurement outcomes and teleported_recipient_state
    is recipient's 1-qubit state post Pauli correction.
    """
    if rng is None:
        rng = np.random.default_rng()

    bell_pair = prepare_bell_pair()
    # 3-qubit joint state: message ⊗ bell_pair (dim 8)
    psi_3q = tensor_product(message_state, bell_pair)

    # Physical attack interaction before Bell measurement
    psi_3q = apply_physical_attack(psi_3q, attack=attack, rng=rng)

    # 1. Apply CNOT between qubit 0 (message) and qubit 1 (sender's Bell half)
    # CNOT on qubits (0, 1) in 3-qubit space
    cnot_3q = np.eye(8, dtype=np.complex128)
    # In binary basis |q0 q1 q2⟩: if q0 == 1, flip q1
    for i in range(8):
        q0 = (i >> 2) & 1
        q1 = (i >> 1) & 1
        q2 = i & 1
        if q0 == 1:
            target_i = ((q0 << 2) | ((1 - q1) << 1) | q2)
            cnot_3q[i, i] = 0.0
            cnot_3q[target_i, i] = 1.0

    psi_1 = cnot_3q @ psi_3q

    # 2. Apply Hadamard on qubit 0 (message qubit)
    h_3q = tensor_product(GATE_H, np.eye(2, dtype=np.complex128), np.eye(2, dtype=np.complex128))
    psi_2 = h_3q @ psi_1

    # 3. Bell measurement on qubits 0 and 1
    # Probabilities for outcomes (b0, b1) = 00, 01, 10, 11
    probs = np.zeros(4, dtype=np.float64)
    sub_states = []

    for b in range(4):
        b0 = (b >> 1) & 1
        b1 = b & 1
        # Projection operator P_{b0, b1} = |b0 b1⟩⟨b0 b1| ⊗ I_bob
        proj = np.zeros((8, 8), dtype=np.complex128)
        for q2 in range(2):
            idx = (b0 << 2) | (b1 << 1) | q2
            proj[idx, idx] = 1.0

        projected_psi = proj @ psi_2
        prob = np.vdot(projected_psi, projected_psi).real
        probs[b] = prob
        sub_states.append(projected_psi)

    # Normalize probabilities
    probs /= np.sum(probs)
    outcome_idx = rng.choice(4, p=probs)
    b0_outcome = (outcome_idx >> 1) & 1
    b1_outcome = outcome_idx & 1

    # Extract recipient's post-measurement 1-qubit state
    collapsed_3q = sub_states[outcome_idx] / np.sqrt(probs[outcome_idx])
    
    # Extract recipient's qubit 2 statevector (dimension 2)
    bob_state = np.zeros(2, dtype=np.complex128)
    for q2 in range(2):
        idx = (b0_outcome << 2) | (b1_outcome << 1) | q2
        bob_state[q2] = collapsed_3q[idx]

    bob_state /= np.linalg.norm(bob_state)

    # 4. Apply Pauli corrections on recipient's qubit
    if apply_correction:
        corrected_bob_state = correct_pauli(bob_state, b0_outcome, b1_outcome)
    else:
        corrected_bob_state = bob_state

    return (b0_outcome, b1_outcome), corrected_bob_state

