import pytest
from dataclasses import FrozenInstanceError
from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.orchestrator import analyze_session
from qsentinel_monitor.quantum_evidence import MonitoringResult


def test_monitor_non_interference():
    """
    CRITICAL NON-INTERFERENCE TEST:
    Asserts that running advisory monitoring produces identical ProtocolDecision outputs:
    A. Running protocol alone
    B. Running protocol + advisory monitor analyze_session
    """
    config = SessionConfig(n_qubits=200, noise_parameter_p=0.03, seed=999)

    # A. Execute protocol alone
    transcript_alone = run_session(config)

    # B. Execute protocol + analyze_session
    transcript_monitored = run_session(config)
    monitored_res = analyze_session(transcript_monitored)

    # 1. Assert protocol decision fields are bit-for-bit identical
    assert transcript_alone.protocol_decision.accepted == transcript_monitored.protocol_decision.accepted
    assert transcript_alone.protocol_decision.reason == transcript_monitored.protocol_decision.reason
    assert transcript_alone.protocol_decision.mismatch_count == transcript_monitored.protocol_decision.mismatch_count
    assert transcript_alone.protocol_decision.sifted_length == transcript_monitored.protocol_decision.sifted_length

    # 2. Assert monitored_res preserves the exact protocol decision as a separate field
    assert monitored_res.protocol_decision == transcript_monitored.protocol_decision
    assert monitored_res.is_advisory is True
    assert isinstance(monitored_res, MonitoringResult)


def test_monitor_cannot_mutate_frozen_transcript():
    """Verify that monitor cannot mutate SessionTranscript or ProtocolDecision."""
    config = SessionConfig(n_qubits=100, seed=55)
    transcript = run_session(config)
    monitored_res = analyze_session(transcript)

    with pytest.raises(FrozenInstanceError):
        monitored_res.protocol_decision.accepted = False

    with pytest.raises(FrozenInstanceError):
        transcript.protocol_decision = None
