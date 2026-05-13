"""Router modules for the API package."""

from .dashboard import router as dashboard_router
from .health import router as health_router
from .models import router as models_router
from .tasks import router as tasks_router

__all__ = [
    "dashboard_router",
    "health_router",
    "models_router",
    "tasks_router",
]
