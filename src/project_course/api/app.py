"""Application factory for the FastAPI service."""

from fastapi import FastAPI

from project_course.api.config import settings
from project_course.api.routers.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    app.include_router(health_router)

    @app.get("/", summary="API root")
    def root() -> dict[str, str]:
        return {"message": "project-course api"}

    return app


app = create_app()
