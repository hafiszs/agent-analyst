"""HTTP API Application Factory and Server Lifecycle.

Clean Architecture Presentation Layer:
- Initializes application components and dependency injection container (app.state).
- Registers CORS middleware and lifespan management.
- Mounts modular routers from app.api.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import Agent
from .api import api_router
from .config import Settings, get_settings
from .jobs import JobManager
from .llm import LLM
from .sandbox import DockerSandbox
from .services import JobService, StorageService

logging.basicConfig(level=logging.INFO)


def create_app(
    settings: Settings | None = None,
    llm: LLM | None = None,
    sandbox: Any | None = None,
) -> FastAPI:
    """Create and configure FastAPI application with Dependency Injection and Lifespan."""
    settings = settings or get_settings()
    llm = llm or LLM(settings)
    sandbox = sandbox or DockerSandbox(settings)
    agent = Agent(llm, sandbox, settings)
    job_manager = JobManager(settings, agent)
    storage_service = StorageService(settings)
    job_service = JobService(job_manager, storage_service, settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if hasattr(sandbox, "cleanup_orphans"):
            sandbox.cleanup_orphans()
        yield

    app = FastAPI(
        title="AI Data Analyst",
        description="Autonomous Multi-Agent Analytical System with Docker Sandboxing",
        lifespan=lifespan,
    )

    # Attach shared dependencies to app.state for FastAPI Dependency Injection
    app.state.settings = settings
    app.state.llm = llm
    app.state.sandbox = sandbox
    app.state.agent = agent
    app.state.job_manager = job_manager
    app.state.storage_service = storage_service
    app.state.job_service = job_service

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register modular API routes under /api
    app.include_router(api_router)

    return app


# Run with:  uvicorn app.main:create_app --factory
