"""
Phase 11 FastAPI Configuration & Dependencies for QSENTINEL.
"""
import os
from typing import Optional, Generator
from fastapi import Request, Depends


DEFAULT_DB_PATH = os.path.join(os.getcwd(), "data", "qsentinel_production.db")


class APISettings:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("QSENTINEL_DB_PATH", DEFAULT_DB_PATH)


def get_settings(request: Request) -> APISettings:
    """Dependency provider for API settings (supports app state injection in tests)."""
    if hasattr(request.app.state, "settings") and request.app.state.settings:
        return request.app.state.settings
    return APISettings()


def get_db_path(settings: APISettings = Depends(get_settings)) -> str:
    """Dependency provider returning the target database path."""
    return settings.db_path
