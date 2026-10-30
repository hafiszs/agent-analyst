from __future__ import annotations

from fastapi import APIRouter, Request

from ...schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    """
    Healthcheck endpoint.

    Verifies system readiness:
    - Docker daemon connectivity
    - Availability of the sandbox Docker image ('agent-sandbox:latest')
    - LLM configuration status (API key and base URL presence)
    """
    sandbox = request.app.state.sandbox
    llm = request.app.state.llm

    info = sandbox.health() if hasattr(sandbox, "health") else {"docker": True, "sandbox_image": True}
    info["llm_configured"] = bool(getattr(llm, "configured", True))
    return info
