"""
Immutable domain objects for QDS session execution.
SessionTranscript and ProtocolDecision are frozen dataclasses to guarantee
strict non-interference and prevent post-finalization state mutations.
"""
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any


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
    keys: List[int]
    bases: List[int]
    recipient_bases: List[int]
    bell_outcomes: List[Tuple[int, int]]
    raw_measurements: List[int]
    sifted_indices: List[int]
    mismatch_flags: List[bool]
    pauli_corrections_applied: List[Tuple[int, int]]
    protocol_decision: ProtocolDecision
    metadata: Dict[str, Any]
