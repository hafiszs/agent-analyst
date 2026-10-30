from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class JobCreateResponse(BaseModel):
    """Response returned when an analysis job is successfully created or continued."""
    job_id: str


class ArtifactItem(BaseModel):
    """Metadata for a downloadable or visual artifact produced by the agent."""
    name: str
    url: str


class JobSnapshotResponse(BaseModel):
    """Full snapshot of an analysis job state and results."""
    id: str
    status: str
    query: str
    filename: str
    plan: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactItem] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceDetailResponse(BaseModel):
    """Audit detail for a single verified claim cited in the final report."""
    id: str
    title: str | None = None
    kind: str | None = None
    code: str | None = None
    stdout: str | None = None
