"""/api/v1/followups: applications due a follow-up (FR-7)."""

from fastapi import APIRouter

from app import schemas
from app.api.deps import Repo, Today
from app.services import followups as service

router = APIRouter(tags=["followups"])


@router.get("/followups", operation_id="listFollowups", summary="Applications due a follow-up")
def list_followups(repo: Repo, today: Today) -> list[schemas.Application]:
    return [schemas.Application.model_validate(a) for a in service.list_followups(repo, today)]
