"""Request and response bodies, matching components/schemas in openapi.yaml."""

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Health(BaseModel):
    status: str
    version: str


class Ready(BaseModel):
    status: str
