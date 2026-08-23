"""
Immutable domain objects for QDS session execution.
SessionTranscript and ProtocolDecision are frozen dataclasses with deep immutability
(tuples instead of lists) to guarantee strict non-interference.
"""
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Sequence


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
    keys: Tuple[int, ...]
    bases: Tuple[int, ...]
    recipient_bases: Tuple[int, ...]
    bell_outcomes: Tuple[Tuple[int, int], ...]
    raw_measurements: Tuple[int, ...]
    sifted_indices: Tuple[int, ...]
    mismatch_flags: Tuple[bool, ...]
    pauli_corrections_applied: Tuple[Tuple[int, int], ...]
    protocol_decision: ProtocolDecision
    metadata: Dict[str, Any]
