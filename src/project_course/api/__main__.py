"""CLI entrypoint for running the FastAPI server locally."""

from __future__ import annotations

import argparse

import uvicorn

from project_course.api.config import settings


def _run_server(reload: bool) -> None:
    """Start the API server."""
    uvicorn.run(
        "project_course.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
    )


def main() -> None:
    """Start the FastAPI app in normal mode."""
    _run_server(reload=settings.reload)


def dev_main() -> None:
    """Start the FastAPI app in development mode with hot reload."""
    _run_server(reload=True)


def cli() -> None:
    """Command line launcher for selecting API run mode."""
    parser = argparse.ArgumentParser(description="Run project-course FastAPI service")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable hot reload mode.",
    )
    args = parser.parse_args()
    _run_server(reload=args.reload or settings.reload)


if __name__ == "__main__":
    cli()
