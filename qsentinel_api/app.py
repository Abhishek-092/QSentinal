"""
Phase 11 FastAPI Application Factory for QSENTINEL.

Exposes `create_app(db_path=...)` to construct the FastAPI application boundary,
initialize database schema, mount routers under `/api/v1`, and register domain error handlers.
"""
from typing import Optional
from fastapi import FastAPI

from qsentinel_api.dependencies import APISettings
from qsentinel_api.errors import register_error_handlers
from qsentinel_api.routers import (
    health_router,
    streams_router,
    epochs_router,
    sessions_router,
)
from qsentinel_monitor.persistence.database import init_database


def create_app(db_path: Optional[str] = None) -> FastAPI:
    """
    Application factory creating a production-grade FastAPI application.
    Supports clean dependency injection of database path for isolation during testing.
    """
    settings = APISettings(db_path=db_path)
    
    # Initialize SQLite WAL schema at target db_path
    init_database(settings.db_path)

    app = FastAPI(
        title="QSENTINEL API",
        description="Quantum-Inspired Cyber Threat Detection & Monitoring API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Store settings in app state for dependency injection
    app.state.settings = settings

    # Register centralized domain error handlers
    register_error_handlers(app)

    # Mount API routers under /api/v1
    api_v1_prefix = "/api/v1"
    app.include_router(health_router, prefix=api_v1_prefix)
    app.include_router(streams_router, prefix=api_v1_prefix)
    app.include_router(epochs_router, prefix=api_v1_prefix)
    app.include_router(sessions_router, prefix=api_v1_prefix)

    return app
