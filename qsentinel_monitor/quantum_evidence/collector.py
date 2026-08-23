"""
Quantum Evidence Collector for QSENTINEL.
Extracts post-session quantum telemetry from immutable SessionTranscript.
Computes:
1. Mismatch rate m = mismatches / sifted_count
2. Correlation C = 1 - 2*m (the protocol-defined relationship under depolarizing noise)
3. Entropy H = - [m log2(m) + (1-m) log2(1-m)]
4. Pauli correction consistency (verifies bell_outcomes match pauli_corrections_applied)
"""
import numpy as np
from typing import Dict, Any
from qds.transcript import SessionTranscript
from qsentinel_monitor.quantum_evidence.models import QuantumEvidence


class EvidenceExtractionError(ValueError):
    """Raised when transcript contains malformed, NaN/Inf, or mathematically impossible telemetry."""
    pass


def extract_evidence(transcript: SessionTranscript) -> QuantumEvidence:
    """
    Extracts strongly typed immutable QuantumEvidence from a finalized SessionTranscript.
    Validates edge cases: zero/invalid sample sizes, malformed data, NaN/Inf values.
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

    mismatch_count = transcript.protocol_decision.mismatch_count

    if mismatch_count < 0 or mismatch_count > sifted_count:
        raise EvidenceExtractionError(f"Impossible mismatch count {mismatch_count} for sifted length {sifted_count}")

    # 1. Mismatch rate m
    mismatch_rate = float(mismatch_count) / float(sifted_count)

    if np.isnan(mismatch_rate) or np.isinf(mismatch_rate) or not (0.0 <= mismatch_rate <= 1.0):
        raise EvidenceExtractionError(f"Invalid mismatch rate computed: {mismatch_rate}")

    # 2. Correlation C = 1 - 2*m
    # Under honest depolarizing channel E(ρ) = (1-p)ρ + (p/3)(XρX+YρY+ZρZ),
    # the expectation value / spin correlation parameter evaluates to C = 1 - 2*m.
    correlation = 1.0 - 2.0 * mismatch_rate

    # 3. Shannon Entropy H (bits)
    # H(m) = - m log2(m) - (1-m) log2(1-m), with 0 log2 0 = 0 safeguard
    if mismatch_rate <= 0.0 or mismatch_rate >= 1.0:
        entropy = 0.0
    else:
        entropy = float(-mismatch_rate * np.log2(mismatch_rate) - (1.0 - mismatch_rate) * np.log2(1.0 - mismatch_rate))

    if np.isnan(entropy) or np.isinf(entropy):
        raise EvidenceExtractionError(f"Invalid entropy computed: {entropy}")

    # 4. Pauli correction consistency
    # Verifies whether bell_outcomes match pauli_corrections_applied for every qubit
    if len(transcript.bell_outcomes) != sample_count or len(transcript.pauli_corrections_applied) != sample_count:
        raise EvidenceExtractionError("Bell outcome or Pauli correction array length mismatch.")

    consistent_count = sum(
        1 for b_out, p_corr in zip(transcript.bell_outcomes, transcript.pauli_corrections_applied)
        if b_out == p_corr
    )
    pauli_consistency = float(consistent_count) / float(sample_count)

    raw_summary: Dict[str, Any] = {
        "n_qubits": sample_count,
        "sifted_len": sifted_count,
        "mismatch_cnt": mismatch_count,
        "mismatch_rate": mismatch_rate,
        "correlation": correlation,
        "entropy": entropy,
        "pauli_consistency": pauli_consistency,
    }

    return QuantumEvidence(
        session_id=transcript.session_id,
        sample_count=sample_count,
        sifted_count=sifted_count,
        mismatch_count=mismatch_count,
        mismatch_rate=mismatch_rate,
        correlation=correlation,
        entropy=entropy,
        pauli_correction_consistency=pauli_consistency,
        raw_evidence_summary=raw_summary,
    )
