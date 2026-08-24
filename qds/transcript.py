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

        return {
            "keys": list(self.keys),
            "bases": list(self.bases),
            "recipient_bases": list(self.recipient_bases),
            "raw_measurements": list(self.raw_measurements),
            "sifted_indices": list(self.sifted_indices),
            "mismatch_flags": list(self.mismatch_flags),
            "mismatch_rate": mismatch_rate,
            "correlation": correlation,
            "entropy": entropy,
            "pauli_consistency": pauli_consistency,
            "metadata": self.metadata,
        }



