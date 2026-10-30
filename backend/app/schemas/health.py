from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """System readiness and dependency configuration status."""
    docker: bool
    sandbox_image: bool
    llm_configured: bool
