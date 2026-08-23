"""
Phase 11 Epoch Management API Integration Test Suite for QSENTINEL.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from qsentinel_api.app import create_app


@pytest.fixture
def api_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_api_epochs.db")
        app = create_app(db_path=db_path)
        with TestClient(app) as client:
            # Pre-create stream
            client.post("/api/v1/streams", json={"stream_id": "str-1", "description": "Stream 1"})
            yield client


def test_create_retrieve_and_renew_epoch(api_client):
    # 1. Create Epoch
    res = api_client.post("/api/v1/streams/str-1/epochs", json={"calibration_p": 0.02})
    assert res.status_code == 201
    ep = res.json()
    epoch_id = ep["epoch_id"]
    assert ep["epoch_index"] == 1
    assert ep["status"] == "ACTIVE"
    assert ep["calibration_context"]["calibration_p"] == 0.02

    # 2. Retrieve Epoch
    get_res = api_client.get(f"/api/v1/streams/str-1/epochs/{epoch_id}")
    assert get_res.status_code == 200
    assert get_res.json()["epoch_id"] == epoch_id

    # 3. Retrieve Epoch State (Sequence 0)
    st_res = api_client.get(f"/api/v1/streams/str-1/epochs/{epoch_id}/state")
    assert st_res.status_code == 200
    assert st_res.json()["sequence_number"] == 0

    # 4. Renew Epoch
    renew_res = api_client.post(
        f"/api/v1/streams/str-1/epochs/{epoch_id}/renew",
        json={"calibration_p": 0.02, "termination_reason": "MANUAL_RENEWAL"},
    )
    assert renew_res.status_code == 200
    new_ep = renew_res.json()
    assert new_ep["epoch_index"] == 2
    assert new_ep["status"] == "ACTIVE"

    # 5. Verify old epoch status is CLOSED
    old_ep = api_client.get(f"/api/v1/streams/str-1/epochs/{epoch_id}").json()
    assert old_ep["status"] == "CLOSED"
