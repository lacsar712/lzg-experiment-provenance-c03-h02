from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StartRunCommand(BaseModel):
    project: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    dataset_content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    code_commit_sha: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    description: str | None = None
    expected_version: int = 0


class RecordMetricCommand(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    value: float
    step: int = Field(ge=0)
    expected_version: int = Field(ge=1)


class AttachArtifactCommand(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    uri: str = Field(min_length=1, max_length=1024)
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    media_type: str | None = Field(default=None, max_length=128)
    expected_version: int = Field(ge=1)


class CompleteRunCommand(BaseModel):
    result_summary: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1)


class AbortRunCommand(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class RunOut(BaseModel):
    id: UUID
    project: str
    name: str
    status: str
    version: int
    dataset_content_sha256: str
    code_commit_sha: str
    description: str | None
    started_at: datetime
    finished_at: datetime | None
    started_by: str
    metrics_json: list[Any]
    artifacts_json: list[Any]
    result_summary: str | None
    abort_reason: str | None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: UUID
    aggregate_id: UUID
    version: int
    event_type: str
    payload_json: dict[str, Any]
    occurred_at: datetime
    actor: str

    model_config = {"from_attributes": True}


class LineageOut(BaseModel):
    run_id: UUID
    project: str
    name: str
    status: str
    code_commit_sha: str
    dataset_content_sha256: str
    artifacts: list[Any]
    metrics: list[Any]
    result_summary: str | None
    abort_reason: str | None
    started_at: datetime
    finished_at: datetime | None
    started_by: str
    version: int
