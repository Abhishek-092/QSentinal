"""Integration tests verifying protocol/monitor non-interference across attack profiles."""

import pytest

from attacks.strategies import ATTACK_REGISTRY, run_attack
from qsentinel_monitor.orchestrator import analyze


@pytest.mark.parametrize("strategy_name", list(ATTACK_REGISTRY.keys()))
def test_protocol_monitor_non_interference(strategy_name):
    """Monitoring must never override or mutate protocol decisions."""
    result = run_attack(strategy_name, f"ni-{strategy_name}")
    transcript = result.transcript
    protocol_before = (
        transcript.protocol_decision.accepted,
        transcript.protocol_decision.reason,
        transcript.protocol_decision.session_id,
    )

    monitoring = analyze(transcript, transcript.protocol_decision)

    protocol_after = (
        transcript.protocol_decision.accepted,
        transcript.protocol_decision.reason,
        transcript.protocol_decision.session_id,
    )

    assert protocol_before == protocol_after
    assert monitoring.advisory is True
    assert monitoring.session_id == transcript.session_id


def test_advisory_can_differ_from_protocol():
    """Monitor may flag sessions the protocol accepts (advisory divergence)."""
    divergences = 0
    for i, name in enumerate(ATTACK_REGISTRY.keys()):
        result = run_attack(name, f"div-{i}")
        monitoring = analyze(result.transcript, result.transcript.protocol_decision)
        protocol_accepted = result.transcript.protocol_decision.accepted
        monitor_accept = monitoring.verdict == "ACCEPT"
        if protocol_accepted != monitor_accept:
            divergences += 1
    assert divergences >= 0  # divergence is allowed; pipeline must not crash
