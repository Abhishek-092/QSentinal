"""
Phase 11 Stream Management API Integration Test Suite for QSENTINEL.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from qsentinel_api.app import create_app


@pytest.fixture
def api_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_api_streams.db")
        app = create_app(db_path=db_path)
        with TestClient(app) as client:
            yield client


def test_create_and_retrieve_stream(api_client):
    # 1. Create Stream
    payload = {"stream_id": "stream-sender-recipient-01", "description": "Test QDS Stream"}
    res = api_client.post("/api/v1/streams", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["stream_id"] == "stream-sender-recipient-01"
    assert data["description"] == "Test QDS Stream"
    assert data["status"] == "ACTIVE"

    # 2. Retrieve Stream
    get_res = api_client.get("/api/v1/streams/stream-sender-recipient-01")
    assert get_res.status_code == 200
    assert get_res.json()["stream_id"] == "stream-sender-recipient-01"


def test_get_unknown_stream_returns_404(api_client):
    res = api_client.get("/api/v1/streams/unknown-stream-999")
    assert res.status_code == 404
