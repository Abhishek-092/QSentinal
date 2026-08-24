"""
Centralized Domain-to-HTTP Exception Mapping for QSENTINEL.

Maps domain exceptions (ConflictingSessionIdError, CryptographicIntegrityError, EpochClosedError, etc.)
to structured JSON responses with explicit HTTP status codes.
"""
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from qsentinel_monitor.persistence.models import (
    CryptographicIntegrityError,
    ProvenanceMismatchError,
    DuplicateSessionError,
    ConflictingSessionIdError,
    EpochClosedError,
)


def register_error_handlers(app: FastAPI) -> None:
    """Registers exception handlers mapping domain failures to HTTP responses."""

    @app.exception_handler(ConflictingSessionIdError)
    async def handle_conflicting_session_id(request: Request, exc: ConflictingSessionIdError):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CONFLICTING_SESSION_ID",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(DuplicateSessionError)
    async def handle_duplicate_session(request: Request, exc: DuplicateSessionError):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "DUPLICATE_SESSION",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(EpochClosedError)
    async def handle_epoch_closed(request: Request, exc: EpochClosedError):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "EPOCH_CLOSED",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(ProvenanceMismatchError)
    async def handle_provenance_mismatch(request: Request, exc: ProvenanceMismatchError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "PROVENANCE_MISMATCH",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(CryptographicIntegrityError)
    async def handle_integrity_error(request: Request, exc: CryptographicIntegrityError):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    "message": "Cryptographic payload integrity verification failed.",
                }
            },
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "UNPROCESSABLE_ENTITY",
                    "message": str(exc),
                }
            },
        )
