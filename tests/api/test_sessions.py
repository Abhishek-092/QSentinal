"""
Phase 11 Session Submission & Error Mapping API Integration Test Suite for QSENTINEL.
"""
import os
import tempfile
import pytest
from dataclasses import asdict
from fastapi.testclient import TestClient

from qds.protocol import run_session, SessionConfig
from qsentinel_api.app import create_app


@pytest.fixture
def api_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_api_sessions.db")
        app = create_app(db_path=db_path)
        with TestClient(app) as client:
            client.post("/api/v1/streams", json={"stream_id": "str-1", "description": "Stream 1"})
            ep_res = client.post("/api/v1/streams/str-1/epochs", json={"calibration_p": 0.02})
            epoch_id = ep_res.json()["epoch_id"]
            yield client, epoch_id


def _transcript_to_dict(tr):
    d = asdict(tr)
    # Ensure lists for JSON payload
    d["keys"] = list(d["keys"])
    d["bases"] = list(d["bases"])
    d["recipient_bases"] = list(d["recipient_bases"])
    d["bell_outcomes"] = [list(x) for x in d["bell_outcomes"]]
    d["raw_measurements"] = list(d["raw_measurements"])
    d["sifted_indices"] = list(d["sifted_indices"])
    d["mismatch_flags"] = list(d["mismatch_flags"])
    d["pauli_corrections_applied"] = [list(x) for x in d["pauli_corrections_applied"]]
    return d


def test_session_submission_pipeline_and_idempotency(api_setup):
    client, epoch_id = api_setup
    tr1 = run_session(SessionConfig(noise_parameter_p=0.02, seed=1, nonce="n1"))
    tr1_dict = _transcript_to_dict(tr1)

    # 1. Post valid session
    res = client.post(f"/api/v1/streams/str-1/epochs/{epoch_id}/sessions", json={"transcript": tr1_dict})
    assert res.status_code == 200
    data = res.json()
    assert data["sequence_number"] == 1
    assert data["threat_assessment"]["security_posture"] == "NOMINAL"

    # 2. Re-submit exact same session (Idempotent duplicate return)
    dup_res = client.post(f"/api/v1/streams/str-1/epochs/{epoch_id}/sessions", json={"transcript": tr1_dict})
    assert dup_res.status_code == 200
    assert dup_res.json()["sequence_number"] == 1

    # 3. Conflicting Session ID submission (HTTP 409 Conflict)
    conflicting_dict = dict(tr1_dict)
    conflicting_dict["nonce"] = "n1_CONFLICTING"
    conflict_res = client.post(
        f"/api/v1/streams/str-1/epochs/{epoch_id}/sessions", json={"transcript": conflicting_dict}
    )
    assert conflict_res.status_code == 409
    assert conflict_res.json()["error"]["code"] == "CONFLICTING_SESSION_ID"

    # 4. Query Monitoring State endpoint
    st_res = client.get(f"/api/v1/streams/str-1/epochs/{epoch_id}/state")
    assert st_res.status_code == 200
    assert st_res.json()["sequence_number"] == 1

    # 5. Query Latest Threat Assessment endpoint
    ta_res = client.get(f"/api/v1/streams/str-1/epochs/{epoch_id}/assessment")
    assert ta_res.status_code == 200
    assert ta_res.json()["security_posture"] == "NOMINAL"
