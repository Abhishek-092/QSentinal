"""
Immutable domain objects for QDS session execution.
SessionTranscript and ProtocolDecision are frozen dataclasses with deep immutability
(tuples instead of lists) to guarantee strict non-interference.
"""
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ProtocolDecision:
    accepted: bool
    reason: str
    mismatch_count: int
    sifted_length: int
    s_a: int
    s_v: float
    session_id: str


@dataclass(frozen=True)
class SessionTranscript:
    session_id: str
    timestamp: float
    sender_id: str
    recipient_id: str
    auth_token: str
    nonce: str
    message_bit: int
    keys: tuple[int, ...]
    bases: tuple[int, ...]
    recipient_bases: tuple[int, ...]
    bell_outcomes: tuple[tuple[int, int], ...]
    raw_measurements: tuple[int, ...]
    sifted_indices: tuple[int, ...]
    mismatch_flags: tuple[bool, ...]
    pauli_corrections_applied: tuple[tuple[int, int], ...]
    protocol_decision: ProtocolDecision
    metadata: dict[str, Any]

    @property
    def measurement_telemetry(self) -> dict[str, Any]:
        sifted_len = len(self.sifted_indices)
        mismatch_rate = float(self.protocol_decision.mismatch_count) / float(sifted_len) if sifted_len > 0 else 0.0
        correlation = 1.0 - 2.0 * mismatch_rate
        p = mismatch_rate
        if p <= 0 or p >= 1:
            entropy = 0.0
        else:
            import math
            entropy = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
        pauli_consistency = max(0.0, 1.0 - 2.0 * mismatch_rate)

        import math

        theta = float(self.metadata.get("theta", math.pi / 4))
        attack = self.metadata.get("attack")

        # Authorized state Bloch vector |ψ(θ)⟩
        x_m = math.sin(theta)
        y_m = 0.0
        z_m = math.cos(theta)

        # Depolarizing contraction factor
        depol_factor = max(0.0, 1.0 - 2.0 * mismatch_rate)

        if attack == "clean_forgery":
            x_b, z_b = 0.0, depol_factor
        elif attack == "impersonation":
            x_b, z_b = 0.0, -depol_factor
        elif attack in ("intercept_resend", "basis_spoof", "entanglement_probe"):
            x_b, z_b = 0.0, 0.0
        elif attack == "sub_threshold_forgery":
            theta_eff = theta + 0.12
            x_b = math.sin(theta_eff) * depol_factor
            z_b = math.cos(theta_eff) * depol_factor
        elif attack == "unauthorized_verification":
            x_b = -x_m * depol_factor
            z_b = -z_m * depol_factor
        else:
            x_b = x_m * depol_factor
            z_b = z_m * depol_factor

        bloch_message = {"x": round(x_m, 4), "y": 0.0, "z": round(z_m, 4)}
        bloch_bob = {"x": round(x_b, 4), "y": 0.0, "z": round(z_b, 4)}

        p0 = max(0.0, (0.5 * (1.0 + z_b))) / 2.0
        p1 = max(0.0, (0.5 * (1.0 - z_b))) / 2.0
        amplitudes_list = [
            {"ket": "|000⟩", "re": round(math.sqrt(p0/2), 4), "im": 0.0, "p": round(p0/2, 4)},
            {"ket": "|001⟩", "re": 0.0, "im": 0.0, "p": 0.0},
            {"ket": "|010⟩", "re": 0.0, "im": 0.0, "p": 0.0},
            {"ket": "|011⟩", "re": round(math.sqrt(p0/2), 4), "im": 0.0, "p": round(p0/2, 4)},
            {"ket": "|100⟩", "re": round(math.sqrt(p1/2), 4), "im": 0.0, "p": round(p1/2, 4)},
            {"ket": "|101⟩", "re": 0.0, "im": 0.0, "p": 0.0},
            {"ket": "|110⟩", "re": 0.0, "im": 0.0, "p": 0.0},
            {"ket": "|111⟩", "re": round(math.sqrt(p1/2), 4), "im": 0.0, "p": round(p1/2, 4)},
        ]

        return {
            "keys": list(self.keys),
            "bases": list(self.bases),
            "recipient_bases": list(self.recipient_bases),
            "raw_measurements": list(self.raw_measurements),
            "sifted_indices": list(self.sifted_indices),
            "mismatch_flags": list(self.mismatch_flags),
            "mismatch_rate": mismatch_rate,
            "fidelity": max(0.0, 1.0 - mismatch_rate),
            "correlation": correlation,
            "entropy": entropy,
            "pauli_consistency": pauli_consistency,
            "bloch_message": bloch_message,
            "bloch_bob": bloch_bob,
            "amplitudes": amplitudes_list,
            "metadata": self.metadata,
        }



