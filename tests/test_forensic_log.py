"""Forensic log tests."""

import json
from pathlib import Path

import pytest

from qds.protocol import run_session
from qsentinel_monitor.forensic_log import LOG_FILE, append_log_entry, verify_chain
from qsentinel_monitor.orchestrator import analyze


@pytest.fixture(autouse=True)
def clean_log(tmp_path, monkeypatch):
    import qsentinel_monitor.forensic_log as fl

    log_file = tmp_path / "forensic_chain.jsonl"
    key_file = tmp_path / "signing_key.pem"
    monkeypatch.setattr(fl, "LOG_FILE", log_file)
    monkeypatch.setattr(fl, "KEY_FILE", key_file)
    monkeypatch.setattr(fl, "FORENSIC_DIR", tmp_path)
    yield


def test_append_and_verify_chain():
    transcript = run_session("forensic-test")
    monitoring = analyze(transcript, transcript.protocol_decision)
    append_log_entry(transcript.protocol_decision, monitoring, transcript.measurement_telemetry)
    result = verify_chain()
    assert result["valid"] is True
    assert result["entries"] == 1


def test_hash_chain_links_entries():
    for i in range(3):
        t = run_session(f"chain-{i}")
        m = analyze(t, t.protocol_decision)
        append_log_entry(t.protocol_decision, m, t.measurement_telemetry)
    result = verify_chain()
    assert result["valid"] is True
    assert result["entries"] == 3
