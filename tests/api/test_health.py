"""
Phase 11 FastAPI Health & Status API Integration Test Suite for QSENTINEL.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from qsentinel_api.app import create_app


@pytest.fixture
def api_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_api_health.db")
        app = create_app(db_path=db_path)
        with TestClient(app) as client:
            yield client


def test_health_check_liveness(api_client):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_database_connectivity(api_client):
    response = api_client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database_status": "connected"}
