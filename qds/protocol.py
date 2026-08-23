"""
QS-L Teleportation-Distributed Quantum Digital Signature Protocol Verification Core.
Executes protocol sessions and enforces the authoritative asymmetric threshold rule: s_a < s_v.
Output arrays are stored as immutable tuples in SessionTranscript.
"""
from dataclasses import dataclass
from typing import Optional
import time
import uuid
import numpy as np

from qds.pauli import encode_eigenstate
from qds.teleportation import teleport
from qds.measurement import project_measurement
from qds.noise import depolarize
from qds.transcript import ProtocolDecision, SessionTranscript


@dataclass
class SessionConfig:
    n_qubits: int = 200
    noise_parameter_p: float = 0.02
    message_bit: int = 1
    s_a_threshold: Optional[int] = None
    s_v_threshold: Optional[float] = None
    sender_id: str = "Alice"
    recipient_id: str = "Bob"
    auth_token: str = "valid_token_001"
    nonce: Optional[str] = None
    seed: Optional[int] = None


def run_session(config: SessionConfig) -> SessionTranscript:
    """
    Orchestrates one complete teleportation-distributed QS-L signature session.
    1. Key & basis generation
    2. Pauli eigenstate encoding
    3. Quantum teleportation over noisy channel
    4. Recipient measurement & BB84 sifting
    5. Asymmetric threshold verification (s_a < s_v)
    6. Assembles & returns frozen SessionTranscript with immutable tuples.
    """
    rng = np.random.default_rng(config.seed)
    session_id = str(uuid.uuid4())
    nonce = config.nonce or str(uuid.uuid4())

    keys = [int(rng.integers(0, 2)) for _ in range(config.n_qubits)]
    bases = [int(rng.integers(0, 2)) for _ in range(config.n_qubits)]
    recipient_bases = [int(rng.integers(0, 2)) for _ in range(config.n_qubits)]

    bell_outcomes = []
    raw_measurements = []
    pauli_corrections = []

    for i in range(config.n_qubits):
        state_i = encode_eigenstate(keys[i], bases[i])
        bell_bits, bob_state = teleport(state_i, rng=rng)
        bell_outcomes.append(bell_bits)
        pauli_corrections.append(bell_bits)

        noisy_bob_state = depolarize(bob_state, p=config.noise_parameter_p, rng=rng)
        meas_bit = project_measurement(noisy_bob_state, basis=recipient_bases[i], rng=rng)
        raw_measurements.append(meas_bit)

    # BB84 sifting: match where sender basis == recipient basis
    sifted_indices = [i for i in range(config.n_qubits) if bases[i] == recipient_bases[i]]
    mismatch_flags = []
    mismatch_count = 0

    for idx in sifted_indices:
        is_mismatch = (keys[idx] != raw_measurements[idx])
        mismatch_flags.append(is_mismatch)
        if is_mismatch:
            mismatch_count += 1

    sifted_len = len(sifted_indices)

    # Asymmetric threshold rule: s_a < s_v
    s_a = config.s_a_threshold if config.s_a_threshold is not None else int(np.floor(0.15 * sifted_len))
    s_v = config.s_v_threshold if config.s_v_threshold is not None else (0.30 * sifted_len)

    accepted = (mismatch_count <= s_a) and (s_a < s_v)
    reason = "Deterministic threshold s_a < s_v satisfied" if accepted else f"Mismatch count {mismatch_count} exceeds s_a threshold {s_a}"

    protocol_decision = ProtocolDecision(
        accepted=accepted,
        reason=reason,
        mismatch_count=mismatch_count,
        sifted_length=sifted_len,
        s_a=s_a,
        s_v=s_v,
        session_id=session_id
    )

    transcript = SessionTranscript(
        session_id=session_id,
        timestamp=time.time(),
        sender_id=config.sender_id,
        recipient_id=config.recipient_id,
        auth_token=config.auth_token,
        nonce=nonce,
        message_bit=config.message_bit,
        keys=tuple(keys),
        bases=tuple(bases),
        recipient_bases=tuple(recipient_bases),
        bell_outcomes=tuple(bell_outcomes),
        raw_measurements=tuple(raw_measurements),
        sifted_indices=tuple(sifted_indices),
        mismatch_flags=tuple(mismatch_flags),
        pauli_corrections_applied=tuple(pauli_corrections),
        protocol_decision=protocol_decision,
        metadata={"noise_parameter_p": config.noise_parameter_p}
    )

    return transcript
