"""GLR-CUSUM unconditional cross-session drift monitor."""

from __future__ import annotations

import math
from dataclasses import dataclass

from db.models import CusumState, get_session_factory


@dataclass(frozen=True)
class CusumUpdate:
    session_id: str
    cusum_value: float
    drift_detected: bool
    log_likelihood_ratio: float


class GLRCusumMonitor:
    """Persists CUSUM state exclusively in SQLite."""

    THRESHOLD = 2.0
    DRIFT = 0.01

    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def update(self, session_id: str, mismatch_rate: float) -> CusumUpdate:
        with self._session_factory() as db:
            state = db.query(CusumState).order_by(CusumState.id.desc()).first()
            prev_cusum = state.cusum_value if state else 0.0

            llr = math.log(max(mismatch_rate, 1e-9) / max(self.DRIFT, 1e-9))
            new_cusum = max(0.0, prev_cusum + llr - 0.5)
            drift_detected = new_cusum >= self.THRESHOLD

            record = CusumState(
                session_id=session_id,
                cusum_value=new_cusum,
                log_likelihood_ratio=llr,
                drift_detected=drift_detected,
            )
            db.add(record)
            db.commit()

            return CusumUpdate(
                session_id=session_id,
                cusum_value=new_cusum,
                drift_detected=drift_detected,
                log_likelihood_ratio=llr,
            )

    def get_history(self, limit: int = 50) -> list[dict]:
        with self._session_factory() as db:
            rows = (
                db.query(CusumState)
                .order_by(CusumState.id.desc())
                .limit(limit)
                .all()
            )
            rows.reverse()
            return [
                {
                    "session": r.id,
                    "session_id": r.session_id,
                    "cusum": round(r.cusum_value, 4),
                    "drift_detected": r.drift_detected,
                }
                for r in rows
            ]
