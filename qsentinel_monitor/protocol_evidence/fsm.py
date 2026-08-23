"""Protocol evidence FSM — freshness, authorization scope, and sequencing checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class FSMResult:
    passed: bool
    checks: dict[str, bool]
    details: str


class ProtocolFSM:
    """Finite-state machine enforcing protocol evidence invariants."""

    def __init__(self) -> None:
        self._last_sequence: dict[str, int] = {}
        self._session_timestamps: dict[str, datetime] = {}

    def check(
        self,
        session_id: str,
        sequence_num: int,
        authorized_scope: str = "verify",
        max_age_seconds: float = 300.0,
    ) -> FSMResult:
        now = datetime.now(timezone.utc)
        checks: dict[str, bool] = {}

        prev_seq = self._last_sequence.get(session_id)
        if prev_seq is None:
            checks["sequencing"] = True
        else:
            checks["sequencing"] = sequence_num == prev_seq + 1
        self._last_sequence[session_id] = sequence_num

        checks["authorization"] = authorized_scope in ("verify", "sign", "audit")
        checks["freshness"] = True

        if session_id in self._session_timestamps:
            age = (now - self._session_timestamps[session_id]).total_seconds()
            checks["freshness"] = age <= max_age_seconds
        self._session_timestamps[session_id] = now

        passed = all(checks.values())
        details = "All FSM invariants satisfied" if passed else f"FSM violation: {checks}"
        return FSMResult(passed=passed, checks=checks, details=details)
