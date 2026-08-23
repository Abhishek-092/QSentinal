"""
Phase 11 Stream Management API Router for QSENTINEL.
"""
from fastapi import APIRouter, Depends, HTTPException
from qsentinel_api.schemas import StreamCreateRequest, StreamResponse
from qsentinel_api.dependencies import get_db_path
from qsentinel_monitor.lifecycle.stream_manager import StreamLifecycleManager
from qsentinel_monitor.persistence.repositories import StreamRepository

router = APIRouter(prefix="/streams", tags=["Stream Management"])


@router.post("", response_model=StreamResponse, status_code=201)
def create_stream(req: StreamCreateRequest, db_path: str = Depends(get_db_path)):
    """Creates a long-lived logical monitoring channel."""
    mgr = StreamLifecycleManager(db_path)
    rec = mgr.create_stream(req.stream_id, req.description or "")
    return StreamResponse(
        stream_id=rec.stream_id,
        description=rec.description,
        created_at=rec.created_at,
        status=rec.status,
    )


@router.get("/{stream_id}", response_model=StreamResponse)
def get_stream(stream_id: str, db_path: str = Depends(get_db_path)):
    """Retrieves public stream information."""
    rec = StreamRepository.get_stream(db_path, stream_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found.")
    return StreamResponse(
        stream_id=rec.stream_id,
        description=rec.description,
        created_at=rec.created_at,
        status=rec.status,
    )
