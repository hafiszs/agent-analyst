from __future__ import annotations

from fastapi import Request

from ..config import Settings
from ..jobs import JobManager
from ..services import JobService, StorageService


def get_settings(request: Request) -> Settings:
    """Dependency provider for application configuration."""
    return request.app.state.settings


def get_storage_service(request: Request) -> StorageService:
    """Dependency provider for storage operations."""
    return request.app.state.storage_service


def get_job_manager(request: Request) -> JobManager:
    """Dependency provider for the core JobManager."""
    return request.app.state.job_manager


def get_job_service(request: Request) -> JobService:
    """Dependency provider for the high-level JobService use case."""
    return request.app.state.job_service
