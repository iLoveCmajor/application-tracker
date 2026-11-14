"""/api/v1/applications: create, read, edit, delete and list (FR-1, FR-2)."""

from uuid import UUID

from fastapi import APIRouter, Response
from fastapi import status as http

from app import schemas
from app.api.deps import Repo
from app.domain import Status
from app.services import applications as service

router = APIRouter(tags=["applications"])


@router.get("/applications", operation_id="listApplications", summary="List applications")
def list_applications(repo: Repo, status: Status | None = None) -> list[schemas.Application]:
    return [schemas.Application.model_validate(a) for a in service.list_applications(repo, status)]


@router.post(
    "/applications",
    operation_id="createApplication",
    summary="Create an application",
    status_code=http.HTTP_201_CREATED,
)
def create_application(body: schemas.ApplicationInput, repo: Repo) -> schemas.Application:
    created = service.create_application(repo, **body.model_dump())
    return schemas.Application.model_validate(created)


@router.get("/applications/{id}", operation_id="getApplication", summary="Get an application")
def get_application(id: UUID, repo: Repo) -> schemas.Application:
    return schemas.Application.model_validate(service.get_application(repo, id))


@router.patch("/applications/{id}", operation_id="updateApplication", summary="Edit an application")
def update_application(id: UUID, body: schemas.ApplicationPatch, repo: Repo) -> schemas.Application:
    updated = service.update_application(repo, id, body.model_dump(exclude_unset=True))
    return schemas.Application.model_validate(updated)


@router.delete(
    "/applications/{id}",
    operation_id="deleteApplication",
    summary="Delete an application",
    status_code=http.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_application(id: UUID, repo: Repo) -> None:
    service.delete_application(repo, id)
