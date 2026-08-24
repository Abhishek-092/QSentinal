import pytest
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
    assert evidence.total_mismatch_count == 0
    assert evidence.overall_mismatch_rate == 0.0
    assert evidence.z_mismatch_rate == 0.0
    assert evidence.x_mismatch_rate == 0.0
    assert evidence.sample_count == 100
    assert evidence.total_sifted_count > 0
    assert evidence.z_sifted_count + evidence.x_sifted_count == evidence.total_sifted_count


def test_evidence_collection_low_noise_session():
    """Verify evidence calculations on a low-noise session (p=0.05)."""
    config = SessionConfig(n_qubits=400, noise_parameter_p=0.05, seed=101)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)

    assert evidence.total_sifted_count > 0
    assert evidence.z_sifted_count > 0
    assert evidence.x_sifted_count > 0
    assert evidence.z_mismatch_count + evidence.x_mismatch_count == evidence.total_mismatch_count


def test_evidence_collection_deep_immutability():
    """Verify that QuantumEvidence is a frozen dataclass."""
    config = SessionConfig(n_qubits=50, seed=1)
    transcript = run_session(config)
    evidence = extract_evidence(transcript)

    with pytest.raises(FrozenInstanceError):
        evidence.overall_mismatch_rate = 0.5


def test_evidence_collection_malformed_transcript_rejection():
    """Verify exception handling for zero samples, invalid counts, or malformed data."""
    with pytest.raises(EvidenceExtractionError):
        extract_evidence(None)

    protocol_dec = ProtocolDecision(
        accepted=True, reason="ok", mismatch_count=-1, sifted_length=0, s_a=5, s_v=10, session_id="err"
    )
    bad_transcript = SessionTranscript(
        session_id="err", timestamp=0.0, sender_id="test-sender", recipient_id="test-recipient", auth_token="test-token", nonce="test-nonce",
        message_bit=0, keys=(), bases=(), recipient_bases=(), bell_outcomes=(), raw_measurements=(),
        sifted_indices=(), mismatch_flags=(), pauli_corrections_applied=(), protocol_decision=protocol_dec, metadata={}
    )
    with pytest.raises(EvidenceExtractionError):
        extract_evidence(bad_transcript)
