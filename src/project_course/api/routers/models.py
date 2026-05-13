"""Model lifecycle APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from project_course.services.model_update_service import (
    IncrementalUpdateRequest,
    ModelUpdateService,
)
from project_course.services.runtime_state import model_registry, update_reports

router = APIRouter(prefix="/api/v1/models", tags=["models"])

_update_service = ModelUpdateService(model_registry)


class IncrementalUpdatePayload(BaseModel):
    base_model_version: str
    new_condition_name: str
    sample_count: int = Field(ge=1)
    session_count: int = Field(default=1, ge=1)


@router.post("/incremental-update", summary="触发增量更新")
def incremental_update(payload: IncrementalUpdatePayload) -> dict[str, str]:
    """Run threshold-guarded incremental update and return job info."""

    req = IncrementalUpdateRequest(
        base_model_version=payload.base_model_version,
        new_condition_name=payload.new_condition_name,
        sample_count=payload.sample_count,
        session_count=payload.session_count,
    )
    try:
        result = _update_service.run_incremental_update(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report = _update_service.build_report(
        before=payload.base_model_version,
        after=result.model_version_after,
    )
    update_reports.append(report)
    return {"update_job_id": result.update_job_id, "status": "accepted"}


@router.get("/versions", summary="查询模型版本列表")
def list_versions() -> dict[str, list[dict[str, str]]]:
    """List registered model versions."""

    versions = [
        {
            "model_version": row.model_version,
            "update_type": row.update_type,
            "created_at": row.created_at,
        }
        for row in model_registry.list_versions()
    ]
    return {"versions": versions}
