"""
Repaired Quantum Evidence Collector for QSENTINEL.
Derives genuinely independent basis-conditioned quantum telemetry from immutable SessionTranscript.
Computes:
1. Z-basis sifted count (n_Z), mismatch count (k_Z), and Z-mismatch rate m_Z = k_Z / n_Z
2. X-basis sifted count (n_X), mismatch count (k_X), and X-mismatch rate m_X = k_X / n_X
3. Total aggregate mismatch rate m
Note: Pauli transmission integrity is deferred per Correction 2 as no distinct transmission boundary exists.
"""
import numpy as np
from typing import Any
from qds.transcript import SessionTranscript
from qsentinel_monitor.quantum_evidence.models import QuantumEvidence


class EvidenceExtractionError(ValueError):
    """Raised when transcript contains malformed, NaN/Inf, or mathematically impossible telemetry."""
    pass


def extract_evidence(transcript: SessionTranscript) -> QuantumEvidence:
    """
    Extracts strongly typed immutable QuantumEvidence from a finalized SessionTranscript.
    Derives independent Z-basis and X-basis telemetry from disjoint sifted qubit sets.
    """
    if not isinstance(transcript, SessionTranscript):
        raise EvidenceExtractionError("Input must be a valid SessionTranscript instance.")

    sample_count = len(transcript.keys)
    sifted_count = len(transcript.sifted_indices)

    if sample_count <= 0:
        raise EvidenceExtractionError(f"Invalid total sample count: {sample_count}")

    if sifted_count <= 0:
        raise EvidenceExtractionError(f"Invalid sifted sample count: {sifted_count}")

    if len(transcript.bases) != sample_count or len(transcript.recipient_bases) != sample_count or len(transcript.raw_measurements) != sample_count:
        raise EvidenceExtractionError("Transcript key/basis/measurement array lengths are inconsistent.")

    # Partition sifted indices into Z-basis (basis == 0) and X-basis (basis == 1)
    z_sifted_indices = [idx for idx in transcript.sifted_indices if transcript.bases[idx] == 0]
    x_sifted_indices = [idx for idx in transcript.sifted_indices if transcript.bases[idx] == 1]

    n_Z = len(z_sifted_indices)
    n_X = len(x_sifted_indices)

    if n_Z + n_X != sifted_count:
        raise EvidenceExtractionError(f"Partition error: n_Z ({n_Z}) + n_X ({n_X}) != total sifted ({sifted_count})")

    # Compute basis-specific mismatch counts
    k_Z = sum(1 for idx in z_sifted_indices if transcript.keys[idx] != transcript.raw_measurements[idx])
    k_X = sum(1 for idx in x_sifted_indices if transcript.keys[idx] != transcript.raw_measurements[idx])
    total_mismatches = transcript.protocol_decision.mismatch_count

    if k_Z + k_X != total_mismatches:
        raise EvidenceExtractionError(f"Mismatch sum mismatch: k_Z ({k_Z}) + k_X ({k_X}) != total ({total_mismatches})")

    m_Z = float(k_Z) / float(n_Z) if n_Z > 0 else 0.0
    m_X = float(k_X) / float(n_X) if n_X > 0 else 0.0
    overall_m = float(total_mismatches) / float(sifted_count)

    for val, name in [(m_Z, "m_Z"), (m_X, "m_X"), (overall_m, "overall_m")]:
        if np.isnan(val) or np.isinf(val) or not (0.0 <= val <= 1.0):
            raise EvidenceExtractionError(f"Invalid rate computed for {name}: {val}")

    raw_summary: dict[str, Any] = {
        "sample_count": sample_count,
        "total_sifted": sifted_count,
        "total_mismatches": total_mismatches,
        "overall_mismatch_rate": overall_m,
        "n_Z": n_Z,
        "k_Z": k_Z,
        "m_Z": m_Z,
        "n_X": n_X,
        "k_X": k_X,
        "m_X": m_X,
    }

    return QuantumEvidence(
        session_id=transcript.session_id,
        sample_count=sample_count,
        total_sifted_count=sifted_count,
        total_mismatch_count=total_mismatches,
        overall_mismatch_rate=overall_m,
        z_sifted_count=n_Z,
        z_mismatch_count=k_Z,
        z_mismatch_rate=m_Z,
        x_sifted_count=n_X,
        x_mismatch_count=k_X,
        x_mismatch_rate=m_X,
        raw_evidence_summary=raw_summary,
    )
