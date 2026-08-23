"""Stage 2: Joint decision engine with calibrated rejection region."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qsentinel_monitor.quantum_evidence.collector import QuantumEvidence
from qsentinel_monitor.stage1 import Stage1Result


@dataclass(frozen=True)
class CalibrationArtifact:
    content_hash: str
    rejection_threshold: float
    s_sprt_threshold: float
    s_gate_threshold: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class Stage2Result:
    s_sprt: float
    s_gate: float
    verdict: str
    passed: bool
    details: str


def load_calibration(path: Path) -> CalibrationArtifact:
    """Load and content-hash-verify calibration artifact."""
    data = json.loads(path.read_text(encoding="utf-8"))
    stored_hash = data.get("content_hash", "")
    payload = {k: v for k, v in data.items() if k != "content_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()
    if stored_hash and stored_hash != content_hash:
        raise ValueError(f"Calibration hash mismatch: expected {stored_hash}, got {content_hash}")
    return CalibrationArtifact(
        content_hash=content_hash,
        rejection_threshold=float(data["rejection_threshold"]),
        s_sprt_threshold=float(data["s_sprt_threshold"]),
        s_gate_threshold=float(data["s_gate_threshold"]),
        metadata=data.get("metadata", {}),
    )


def run_stage2(
    evidence: QuantumEvidence,
    stage1: Stage1Result,
    calibration: CalibrationArtifact,
) -> Stage2Result:
    """Evaluate S_SPRT and S_gate against calibrated rejection region."""
    s_sprt = float(evidence.mismatch_rate / max(stage1.p_hat, 1e-6))
    s_gate = float(
        evidence.correlation * evidence.pauli_consistency * (1.0 - evidence.entropy)
    )

    if s_sprt > calibration.s_sprt_threshold or s_gate < calibration.s_gate_threshold:
        if evidence.mismatch_rate > calibration.rejection_threshold:
            verdict = "FLAG_REJECT"
            details = "Statistical anomaly exceeds joint calibration threshold R."
            passed = False
        else:
            verdict = "FLAG_INVESTIGATE"
            details = "Moderate drift detected by Stage 2 likelihood filter."
            passed = False
    else:
        verdict = "ACCEPT"
        details = "Session statistics conform securely to the honest model H0."
        passed = True

    return Stage2Result(
        s_sprt=s_sprt,
        s_gate=s_gate,
        verdict=verdict,
        passed=passed,
        details=details,
    )
