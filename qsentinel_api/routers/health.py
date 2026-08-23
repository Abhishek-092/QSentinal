"""
Phase 11 Health & Readiness API Router for QSENTINEL.
"""
from fastapi import APIRouter, Depends, HTTPException
from qsentinel_api.schemas import HealthResponse, ReadinessResponse
from qsentinel_api.dependencies import get_db_path
from qsentinel_monitor.persistence.database import get_connection

router = APIRouter(tags=["System Status"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Basic liveness check."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check(db_path: str = Depends(get_db_path)):
    """Verifies operational database connectivity without running calibration simulations."""
    try:
        conn = get_connection(db_path)
        conn.execute("SELECT 1;")
        conn.close()
        return ReadinessResponse(status="ready", database_status="connected")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")
