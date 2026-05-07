"""Health-related endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Health check")
def health_check() -> dict[str, str]:
    """Return the basic health status for the service."""
    return {"status": "ok"}
