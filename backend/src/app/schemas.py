"""Request and response bodies, matching components/schemas in openapi.yaml."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.domain import Source, Status

# Trimmed, then 1–100 characters.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Link = Annotated[str, StringConstraints(max_length=500, pattern=r"^https?://")]
Notes = Annotated[str, StringConstraints(max_length=5000)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- requests ------------------------------------------------------------------


class ApplicationInput(RequestModel):
    company: Name
    role: Name
    source: Source
    link: Link | None = None
    notes: Notes | None = None


class ApplicationPatch(RequestModel):
    """Only the fields present are changed; `null` clears link, notes and the dates.

    company, role and source may be left out but not sent as `null`. Read the
    changes with `model_dump(exclude_unset=True)`. An unknown field, `status`
    included, is a validation error (FR-3).
    """

    company: Name | None = None
    role: Name | None = None
    source: Source | None = None
    link: Link | None = None
    applied_date: date | None = None
    follow_up_date: date | None = None
    notes: Notes | None = None

    @field_validator("company", "role", "source")
    @classmethod
    def not_null[T](cls, value: T | None) -> T:
        # Runs only for values that were sent; a left-out field keeps its default.
        if value is None:
            raise ValueError("must not be null")
        return value


# ---- responses -----------------------------------------------------------------


class Application(ResponseModel):
    id: UUID
    company: str
    role: str
    link: str | None
    source: Source
    status: Status
    applied_date: date | None
    follow_up_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class Health(BaseModel):
    status: str
    version: str


class Ready(BaseModel):
    status: str
