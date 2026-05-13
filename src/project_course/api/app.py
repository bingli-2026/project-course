"""Application factory for the FastAPI service."""

from fastapi import FastAPI

from project_course.api.config import settings
from project_course.api.routers import (
    dashboard_router,
    health_router,
    models_router,
    tasks_router,
)


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    app.include_router(health_router)
    app.include_router(tasks_router)
    app.include_router(dashboard_router)
    app.include_router(models_router)

    @app.get("/", summary="API root")
    def root() -> dict[str, str]:
        return {"message": "project-course api"}

    @app.get("/api/v1/health", summary="Health check alias")
    def health_alias() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
