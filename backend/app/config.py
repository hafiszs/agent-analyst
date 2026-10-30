"""Central configuration, read from environment variables (.env via docker compose)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    # --- LLM: any OpenAI-compatible endpoint (Azure OpenAI /openai/v1, Vultr Serverless Inference, ...)
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    # --- Sandbox (per execution)
    sandbox_image: str
    sandbox_memory_mb: int
    sandbox_cpus: float
    sandbox_timeout_s: int
    sandbox_pids: int
    sandbox_output_mb: int
    # --- Agent
    max_retries: int
    # --- API / jobs
    max_upload_mb: int
    max_concurrent_jobs: int
    job_ttl_s: int
    work_dir: str
    cors_origins: list[str]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        sandbox_image=os.getenv("SANDBOX_IMAGE", "agent-sandbox:latest"),
        sandbox_memory_mb=_int("SANDBOX_MEMORY_MB", 1024),
        sandbox_cpus=_float("SANDBOX_CPUS", 1.0),
        sandbox_timeout_s=_int("SANDBOX_TIMEOUT_S", 60),
        sandbox_pids=_int("SANDBOX_PIDS", 128),
        sandbox_output_mb=_int("SANDBOX_OUTPUT_MB", 100),
        max_retries=_int("MAX_RETRIES", 4),
        max_upload_mb=_int("MAX_UPLOAD_MB", 100),
        max_concurrent_jobs=_int("MAX_CONCURRENT_JOBS", 2),
        job_ttl_s=_int("JOB_TTL_S", 3600),
        # Must be an absolute path that is IDENTICAL on the host and inside the backend container
        # (docker-compose mounts it at the same path) because sandbox containers bind-mount from it.
        work_dir=os.getenv("WORK_DIR", "/srv/agent-work"),
        cors_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()],
    )
