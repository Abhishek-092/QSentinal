"""Unit tests for QSENTINEL monitoring layer."""

from qds.protocol import run_session
from qsentinel_monitor.orchestrator import MonitoringDecision, analyze


def test_analyze_returns_advisory_decision():
    transcript = run_session("monitor-test")
    decision = analyze(transcript, transcript.protocol_decision)
    assert isinstance(decision, MonitoringDecision)
    assert decision.advisory is True
    assert decision.verdict in ("ACCEPT", "FLAG_REJECT", "FLAG_INVESTIGATE", "MODEL_INVALID")


def test_monitoring_never_mutates_protocol_decision():
    transcript = run_session("non-mutate-test", noise_p=0.15)
    original_accepted = transcript.protocol_decision.accepted
    original_reason = transcript.protocol_decision.reason
    analyze(transcript, transcript.protocol_decision)
    assert transcript.protocol_decision.accepted == original_accepted
    assert transcript.protocol_decision.reason == original_reason


def test_high_mismatch_triggers_flag():
    transcript = run_session("high-mismatch", noise_p=0.15)
    decision = analyze(transcript, transcript.protocol_decision)
    assert decision.verdict in ("FLAG_REJECT", "FLAG_INVESTIGATE", "MODEL_INVALID")
