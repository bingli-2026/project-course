"""Application factory for the FastAPI service."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from project_course.api.config import settings
from project_course.api.live.simulator import simulator_lifespan
from project_course.api.routers.dashboard import router as dashboard_router
from project_course.api.routers.health import router as health_router
from project_course.api.routers.history import router as history_router
from project_course.api.routers.tasks import router as tasks_router
from project_course.api.storage import db
from project_course.api.storage.ingest import scan_directory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    orphaned = db.fail_orphaned_running_tasks()
    if orphaned:
        import logging
        logging.getLogger(__name__).warning(
            "marked %d orphaned running task(s) as failed on startup", orphaned,
        )
    scan_directory()  # populate offline history from data/samples/ on startup
    async with simulator_lifespan():
        yield


def create_app() -> FastAPI:
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
    app.include_router(tasks_router)
    app.include_router(dashboard_router)
    app.include_router(history_router)

    @app.get("/", summary="API root")
    def root() -> dict[str, str]:
        return {"message": "project-course api"}

    return app


app = create_app()
