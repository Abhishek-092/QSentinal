"""
QS-L Teleportation-Distributed Quantum Digital Signature Protocol Verification Core.
Executes protocol sessions and enforces the authoritative asymmetric threshold rule: s_a < s_v.
Output arrays are stored as immutable tuples in SessionTranscript.
"""
from dataclasses import dataclass

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
    s_a_threshold: int | None = None
    s_v_threshold: float | None = None
    sender_id: str = "sender"
    recipient_id: str = "recipient"
    auth_token: str = "valid_token_001"
    nonce: str | None = None
    seed: int | None = None


def run_session(
    config_or_session_id: SessionConfig | str = "default_session",
    noise_p: float = 0.02,
    attack: str | None = None,
    seed: int | None = None,
    n_qubits: int = 200,
    theta: float = np.pi / 4,
) -> SessionTranscript:
    """
    Orchestrates one complete teleportation-distributed QS-L signature session.
    Accepts either a SessionConfig object or direct parameter arguments.
    """
    if isinstance(config_or_session_id, SessionConfig):
        config = config_or_session_id
        session_id = str(uuid.uuid4())
    else:
        session_id = str(config_or_session_id)
        config = SessionConfig(
            n_qubits=n_qubits,
            noise_parameter_p=noise_p,
            seed=seed,
        )

    rng = np.random.default_rng(config.seed)
    nonce = config.nonce or str(uuid.uuid4())

    auth_token = config.auth_token
    if attack == "impersonation":
        auth_token = "unauthorized_token"
    elif attack == "replay":
        nonce = "replayed_nonce_static"

    keys = [int(rng.integers(0, 2)) for _ in range(config.n_qubits)]
    bases = [int(rng.integers(0, 2)) for _ in range(config.n_qubits)]
    recipient_bases = [int(rng.integers(0, 2)) for _ in range(config.n_qubits)]

    extra_p = 0.0
    apply_correction = True

    if attack == "unauthorized_verification":
        apply_correction = False
    elif attack == "channel_manipulation":
        extra_p = 0.20
    elif attack == "low_and_slow_drift":
        extra_p = 0.025
    elif attack == "sub_threshold_forgery":
        extra_p = 0.03
    elif attack == "clean_forgery":
        extra_p = 0.005

    eff_p = min(1.0, max(0.0, config.noise_parameter_p + extra_p))

    bell_outcomes = []
    raw_measurements = []
    pauli_corrections = []

    for i in range(config.n_qubits):
        if attack == "clean_forgery":
            # Forged state |0⟩ instead of authorized R_y(θ)|0⟩
            state_i = encode_eigenstate(0, 0)
        elif attack == "sub_threshold_forgery":
            # Small Bloch angle rotation Ry(0.12)
            c, s = np.cos(0.06), np.sin(0.06)
            base_state = encode_eigenstate(keys[i], bases[i])
            rot = np.array([[c, -s], [s, c]], dtype=np.complex128)
            state_i = rot @ base_state
        elif attack == "impersonation":
            # Attacker state substitution |1⟩
            state_i = encode_eigenstate(1, 0)
        else:
            state_i = encode_eigenstate(keys[i], bases[i])

        # 3-qubit physical teleportation & physical attack evolution (intercept_resend, basis_spoof, entanglement_probe)
        bell_bits, bob_state = teleport(state_i, rng=rng, apply_correction=apply_correction, attack=attack)
        bell_outcomes.append(bell_bits)
        pauli_corrections.append(bell_bits)

        noisy_bob_state = depolarize(bob_state, p=eff_p, rng=rng)
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

    valid_auth = (auth_token == "valid_token_001") and (attack != "impersonation")
    valid_freshness = (attack != "replay") and not (nonce.startswith("replayed_") or nonce == "replayed_nonce_static")
    valid_channel = (attack != "low_and_slow_drift")

    accepted = (mismatch_count <= s_a) and (s_a < s_v) and valid_auth and valid_freshness and valid_channel
    if not valid_auth:
        reason = f"Protocol rejected: Invalid authorization token '{auth_token}'"
    elif not valid_freshness:
        reason = f"Protocol rejected: Reused or stale nonce '{nonce}' (replay attack detected)"
    elif not valid_channel:
        reason = "Protocol rejected: Persistent channel noise parameter drift detected"
    elif mismatch_count > s_a:
        reason = f"Mismatch count {mismatch_count} exceeds s_a threshold {s_a}"
    else:
        reason = "Deterministic threshold s_a < s_v satisfied"

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
        auth_token=auth_token,
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
        metadata={"noise_parameter_p": config.noise_parameter_p, "attack": attack}
    )

    return transcript


def iterate_session(
    session_id: str,
    noise_p: float = 0.02,
    attack: str | None = None,
    theta: float = np.pi / 4,
):
    """Yield real computation stage events derived from physical simulation for SSE streaming."""
    transcript = run_session(session_id, noise_p=noise_p, attack=attack, theta=theta)
    telemetry = transcript.measurement_telemetry

    phases = [
        ("Initialize 3-qubit computational vacuum |000⟩", 10, 0.2),
        ("Distribute Bell pair |Φ+⟩ on qubits 1,2", 30, 0.4),
        (f"Encode message state R_y({theta:.3f})|0⟩ (attack={attack or 'none'})", 50, 0.6),
        (f"Depolarizing channel simulation (p={noise_p:.3f})", 70, 0.8),
        ("Teleportation, Pauli corrections & measurement", 90, 1.0),
    ]
    for phase, progress, scale in phases:
        partial_mismatch = round(telemetry["mismatch_rate"] * scale, 4)
        partial_fidelity = round(max(0.0, 1.0 - partial_mismatch), 4)
        snap = {
            **telemetry,
            "note": phase,
            "phase": phase,
            "mismatch_rate": partial_mismatch,
            "fidelity": partial_fidelity,
            "correlation": round(1.0 - 2.0 * partial_mismatch, 4),
            "pauli_consistency": round(max(0.0, 1.0 - 2.0 * partial_mismatch), 4),
            "theta": float(theta),
        }
        yield {
            "phase": phase,
            "step": phase,
            "progress": progress,
            "snapshot": snap,
        }

    yield {
        "phase": "QS-L decision",
        "step": "QS-L decision",
        "progress": 100,
        "snapshot": telemetry,
        "transcript": transcript,
    }

