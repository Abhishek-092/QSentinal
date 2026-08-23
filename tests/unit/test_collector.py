import pytest
import numpy as np
from dataclasses import FrozenInstanceError
from qds.protocol import run_session, SessionConfig
from qds.transcript import SessionTranscript, ProtocolDecision
from qsentinel_monitor.quantum_evidence import extract_evidence, EvidenceExtractionError, QuantumEvidence


def test_evidence_collection_noiseless_session():
    """Verify evidence extraction on a zero mismatch noiseless session."""
    config = SessionConfig(n_qubits=100, noise_parameter_p=0.0, seed=42)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)

    assert isinstance(evidence, QuantumEvidence)
    assert evidence.mismatch_count == 0
    assert evidence.mismatch_rate == 0.0
    assert evidence.correlation == 1.0
    assert evidence.entropy == 0.0
    assert evidence.pauli_correction_consistency == 1.0
    assert evidence.sample_count == 100


def test_evidence_collection_low_noise_session():
    """Verify evidence calculations on a low-noise session (p=0.05)."""
    config = SessionConfig(n_qubits=200, noise_parameter_p=0.05, seed=101)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)

    assert evidence.mismatch_rate > 0.0
    assert pytest.approx(evidence.correlation, 1e-5) == (1.0 - 2.0 * evidence.mismatch_rate)
    assert evidence.entropy > 0.0
    assert evidence.pauli_correction_consistency == 1.0


def test_evidence_collection_immutability():
    """Verify that QuantumEvidence is a frozen dataclass."""
    config = SessionConfig(n_qubits=50, seed=1)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)

    with pytest.raises(FrozenInstanceError):
        evidence.mismatch_rate = 0.5


def test_evidence_collection_malformed_transcript_rejection():
    """Verify exception handling for zero samples, invalid counts, or malformed data."""
    with pytest.raises(EvidenceExtractionError):
        extract_evidence(None)

    # Malformed empty transcript test
    protocol_dec = ProtocolDecision(
        accepted=True, reason="ok", mismatch_count=-1, sifted_length=0, s_a=5, s_v=10, session_id="err"
    )
    bad_transcript = SessionTranscript(
        session_id="err", timestamp=0.0, sender_id="A", recipient_id="B", auth_token="t", nonce="n",
        message_bit=0, keys=[], bases=[], recipient_bases=[], bell_outcomes=[], raw_measurements=[],
        sifted_indices=[], mismatch_flags=[], pauli_corrections_applied=[], protocol_decision=protocol_dec, metadata={}
    )
    with pytest.raises(EvidenceExtractionError):
        extract_evidence(bad_transcript)
