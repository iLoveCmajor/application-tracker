"""/api/v1/stats/funnel: funnel numbers (FR-8)."""

from fastapi import APIRouter

from app import schemas
from app.api.deps import Repo
from app.services import funnel as service

router = APIRouter(tags=["stats"])


@router.get("/stats/funnel", operation_id="getFunnel", summary="Funnel numbers")
def get_funnel(repo: Repo) -> schemas.Funnel:
    funnel = service.get_funnel(repo)
    return schemas.Funnel(
        total=funnel.total,
        by_status=schemas.StatusCounts(**{status.value: n for status, n in funnel.by_status.items()}),
        by_source=[schemas.SourceFunnel.model_validate(row) for row in funnel.by_source],
    )
