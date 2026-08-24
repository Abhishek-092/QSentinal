"""Unit tests for QDS protocol layer."""

import pytest

from qds.protocol import ProtocolDecision, SessionTranscript, run_session


def test_session_transcript_is_frozen():
    transcript = run_session("test-frozen")
    with pytest.raises(Exception):
        transcript.session_id = "mutated"


def test_protocol_decision_is_frozen():
    transcript = run_session("test-decision-frozen")
    with pytest.raises(Exception):
        transcript.protocol_decision.accepted = not transcript.protocol_decision.accepted


def test_run_session_returns_valid_structure():
    transcript = run_session("test-structure", noise_p=0.02)
    assert isinstance(transcript, SessionTranscript)
    assert isinstance(transcript.protocol_decision, ProtocolDecision)
    assert transcript.session_id == "test-structure"
    assert "mismatch_rate" in transcript.measurement_telemetry
    assert "correlation" in transcript.measurement_telemetry
    assert "entropy" in transcript.measurement_telemetry
    assert "pauli_consistency" in transcript.measurement_telemetry


def test_high_noise_tends_to_reject():
    rejections = sum(
        1 for i in range(20)
        if not run_session(f"noise-{i}", noise_p=0.25).protocol_decision.accepted
    )
    assert rejections >= 10
