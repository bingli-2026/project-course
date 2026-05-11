"""Application factory for the FastAPI service."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from project_course.api.config import settings
from project_course.api.routers.health import router as health_router
from project_course.api.routers.samples import router as samples_router
from project_course.api.storage import db
from project_course.api.storage.ingest import scan_directory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    scan_directory()
    yield


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(samples_router)

    @app.get("/", summary="API root")
    def root() -> dict[str, str]:
        return {"message": "project-course api"}

    return app


app = create_app()
