"""
Router Package Initialization.
"""
from qsentinel_api.routers.health import router as health_router
from qsentinel_api.routers.streams import router as streams_router
from qsentinel_api.routers.epochs import router as epochs_router
from qsentinel_api.routers.sessions import router as sessions_router

__all__ = [
    "health_router",
    "streams_router",
    "epochs_router",
    "sessions_router",
]
