"""
Experimental Attack Scenarios & Threat Models for QSENTINEL (Phase 7).

Defines immutable threat models, attack scenario configurations, deterministic
evaluation child seed derivation, and experimental session generation using QDS primitives.
PERFORMS ZERO MODIFICATION TO PRODUCTION QDS OR QSENTINEL MONITOR CODE.
"""
from dataclasses import dataclass
from enum import Enum

import hashlib
import uuid
import numpy as np

from qds.pauli import encode_eigenstate
from qds.teleportation import teleport
from qds.measurement import project_measurement
from qds.noise import depolarize
from qds.transcript import ProtocolDecision, SessionTranscript
from experiments.seed_allocator import SeedAllocator, SeedAllocationError


class AttackType(str, Enum):
    HONEST_BASELINE = "HONEST_BASELINE"
    BASIS_ASYMMETRIC_NOISE = "BASIS_ASYMMETRIC_NOISE"
    Z_BASIS_FLIP = "Z_BASIS_FLIP"
    X_BASIS_FLIP = "X_BASIS_FLIP"
    DELAYED_ATTACK_ONSET = "DELAYED_ATTACK_ONSET"


@dataclass(frozen=True)
class AttackScenario:
    """
    Immutable attack scenario configuration for evaluation.
    """
    scenario_id: str
    attack_type: AttackType
    base_p: float = 0.02
    attack_p_z: float = 0.02
    attack_p_x: float = 0.02
    attack_onset_session: int = 1
    attack_duration: int = 50
    n_qubits: int = 200

    def __post_init__(self):
        if not (0.0 <= self.base_p <= 0.5):
            raise ValueError(f"base_p {self.base_p} must be in [0.0, 0.5]")
        if not (0.0 <= self.attack_p_z <= 0.5):
            raise ValueError(f"attack_p_z {self.attack_p_z} must be in [0.0, 0.5]")
        if not (0.0 <= self.attack_p_x <= 0.5):
            raise ValueError(f"attack_p_x {self.attack_p_x} must be in [0.0, 0.5]")
        if self.attack_onset_session < 1:
            raise ValueError(f"attack_onset_session {self.attack_onset_session} must be >= 1")
        if self.attack_duration < 1:
            raise ValueError(f"attack_duration {self.attack_duration} must be >= 1")
        if self.n_qubits < 10:
            raise ValueError(f"n_qubits {self.n_qubits} must be >= 10")
        if self.attack_type == AttackType.BASIS_ASYMMETRIC_NOISE and self.attack_p_z == self.attack_p_x:
            raise ValueError("BASIS_ASYMMETRIC_NOISE scenario requires attack_p_z != attack_p_x")


def derive_evaluation_child_seed(stream_seed: int, trial_idx: int, session_idx: int) -> int:
    """
    Cryptographically deterministic child-seed derivation for evaluation streams.
    Independent of Python hash randomization or wall clock.
    Returns integer in [0, 2**31 - 1].
    """
    key_str = f"eval_stream:{stream_seed}|trial:{trial_idx}|session:{session_idx}"
    digest = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31 - 1)


def run_experimental_session(
    scenario: AttackScenario,
    session_index: int,
    seed: int,
) -> SessionTranscript:
    """
    Executes one experimental protocol session under the specified AttackScenario configuration.
    Uses QDS primitive functions directly, leaving qds package untouched.
    Returns standard, frozen SessionTranscript compatible with extract_evidence().
    """
    rng = np.random.default_rng(seed)
    session_id = str(uuid.UUID(bytes=rng.bytes(16)))
    nonce = str(uuid.UUID(bytes=rng.bytes(16)))

    # Determine whether attack is active for this session index
    is_attack_active = (
        scenario.attack_onset_session <= session_index < scenario.attack_onset_session + scenario.attack_duration
    ) and (scenario.attack_type != AttackType.HONEST_BASELINE)

    effective_p_z = scenario.attack_p_z if is_attack_active else scenario.base_p
    effective_p_x = scenario.attack_p_x if is_attack_active else scenario.base_p

    keys = [int(rng.integers(0, 2)) for _ in range(scenario.n_qubits)]
    bases = [int(rng.integers(0, 2)) for _ in range(scenario.n_qubits)]
    recipient_bases = [int(rng.integers(0, 2)) for _ in range(scenario.n_qubits)]

    bell_outcomes = []
    raw_measurements = []
    pauli_corrections = []

    for i in range(scenario.n_qubits):
        state_i = encode_eigenstate(keys[i], bases[i])
        bell_bits, bob_state = teleport(state_i, rng=rng)
        bell_outcomes.append(bell_bits)
        pauli_corrections.append(bell_bits)

        # Apply basis-conditioned noise channel
        # basis 0 = Z basis (affected by p_z noise), basis 1 = X basis (affected by p_x noise)
        p_channel = effective_p_z if recipient_bases[i] == 0 else effective_p_x
        noisy_bob_state = depolarize(bob_state, p=p_channel, rng=rng)

        meas_bit = project_measurement(noisy_bob_state, basis=recipient_bases[i], rng=rng)
        raw_measurements.append(meas_bit)

    # BB84 sifting: match where sender basis == recipient basis
    sifted_indices = [i for i in range(scenario.n_qubits) if bases[i] == recipient_bases[i]]
    mismatch_flags = []
    mismatch_count = 0

    for idx in sifted_indices:
        is_mismatch = (keys[idx] != raw_measurements[idx])
        mismatch_flags.append(is_mismatch)
        if is_mismatch:
            mismatch_count += 1

    sifted_len = len(sifted_indices)

    # Standard threshold logic
    s_a = int(np.floor(0.15 * sifted_len))
    s_v = 0.30 * sifted_len

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

    return SessionTranscript(
        session_id=session_id,
        timestamp=1700000000.0,  # Fixed deterministic timestamp for experimental runs
        sender_id="sender",
        recipient_id="recipient",
        auth_token="eval_token_001",
        nonce=nonce,
        message_bit=1,
        keys=tuple(keys),
        bases=tuple(bases),
        recipient_bases=tuple(recipient_bases),
        bell_outcomes=tuple(bell_outcomes),
        raw_measurements=tuple(raw_measurements),
        sifted_indices=tuple(sifted_indices),
        mismatch_flags=tuple(mismatch_flags),
        pauli_corrections_applied=tuple(pauli_corrections),
        protocol_decision=protocol_decision,
        metadata={
            "noise_parameter_p": scenario.base_p,
            "effective_p_z": effective_p_z,
            "effective_p_x": effective_p_x,
            "is_attack_active": is_attack_active,
        }
    )
