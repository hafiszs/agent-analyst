from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from ..config import Settings
from ..jobs import Job, JobManager
from .storage_service import StorageService

log = logging.getLogger(__name__)


class JobService:
    """Application service orchestrating job creation, session chaining, and result querying."""

    def __init__(self, manager: JobManager, storage: StorageService, settings: Settings):
        self.manager = manager
        self.storage = storage
        self.settings = settings

    @staticmethod
    def validate_query(query: str) -> str:
        """Validate user query string constraints."""
        clean = (query or "").strip()
        if not clean:
            raise HTTPException(status_code=400, detail="Query is empty")
        if len(clean) > 1000:
            raise HTTPException(status_code=400, detail="Query is too long (max 1000 characters)")
        return clean

    def get_job_or_404(self, job_id: str) -> Job:
        """Retrieve active or buffered job by ID, or raise HTTP 404."""
        job = self.manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    async def create_analysis_job(self, query: str, incoming_files: list[UploadFile]) -> Job:
        """Process uploaded files, validate query, and start a new analysis pipeline."""
        valid_query = self.validate_query(query)

        if not incoming_files:
            raise HTTPException(status_code=400, detail="No file uploaded")

        files_data: list[dict[str, Any]] = []
        for f in incoming_files:
            data = await self.storage.process_upload_file(f)
            files_data.append(data)

        return self.manager.create(files=files_data, query=valid_query)

    async def continue_analysis_job(
        self,
        job_id: str,
        query: str,
        new_files: list[UploadFile],
        history: list[dict[str, str]] | None = None,
    ) -> Job:
        """Continue an existing conversation, re-using prior datasets and conversation context."""
        valid_query = self.validate_query(query)
        old_job = self.get_job_or_404(job_id)

        # 1. Discover existing original datasets from prior turn
        old_files = [p for p in old_job.data_dir.iterdir() if p.is_file() and not p.name.startswith(".")]
        if not old_files:
            raise HTTPException(status_code=404, detail="Original datasets not found")

        non_raw = [p for p in old_files if not p.name.startswith("raw.") and p.name != "clean.csv"]
        target_old = non_raw if non_raw else [p for p in old_files if not p.name.startswith("raw.")]
        if not target_old:
            target_old = old_files

        files_data: list[dict[str, Any]] = [
            {"filename": p.name, "content": p.read_bytes(), "ext": p.suffix.lower()}
            for p in target_old
        ]

        # 2. Process and merge any newly uploaded files
        for f in new_files:
            data = await self.storage.process_upload_file(f)
            existing_idx = next((i for i, item in enumerate(files_data) if item["filename"] == data["filename"]), None)
            if existing_idx is not None:
                files_data[existing_idx] = data
            else:
                files_data.append(data)

        # 3. Construct / propagate multi-turn conversation history
        accumulated_history: list[dict[str, str]] = []
        if history and isinstance(history, list):
            for item in history:
                if isinstance(item, dict) and item.get("role") and item.get("content"):
                    accumulated_history.append({"role": str(item["role"]), "content": str(item["content"])})
        else:
            accumulated_history = list(getattr(old_job, "history", []) or [])
            old_summary = ""
            if old_job.report:
                old_summary = old_job.report.get("headline") or old_job.report.get("summary") or ""
                if not old_summary and old_job.report.get("verified_claims"):
                    claims = [c.get("text", "") for c in old_job.report.get("verified_claims", []) if c.get("text")]
                    old_summary = "; ".join(claims[:3])
            accumulated_history.append({"role": "user", "content": old_job.query})
            if old_summary:
                accumulated_history.append({"role": "assistant", "content": old_summary})

        new_job = self.manager.create(files=files_data, query=valid_query, history=accumulated_history)

        # 4. Propagate previously cleaned dataset if present to accelerate analysis
        clean_path = old_job.data_dir / "clean.csv"
        if not clean_path.is_file() and "clean.csv" in old_job.artifacts:
            clean_path = old_job.artifacts["clean.csv"]

        if clean_path.is_file():
            new_clean = new_job.data_dir / "clean.csv"
            if not new_clean.exists():
                self.storage.copy_file_safe(clean_path, new_clean)

        return new_job

    def get_job_snapshot(self, job_id: str) -> dict[str, Any]:
        """Produce serialized snapshot of job state for UI polling and state restoration."""
        job = self.get_job_or_404(job_id)
        return {
            "id": job.id,
            "status": job.status,
            "query": job.query,
            "filename": job.filename,
            "plan": job.plan,
            "report": job.report,
            "warnings": job.warnings,
            "artifacts": [{"name": n, "url": f"/api/jobs/{job.id}/files/{n}"} for n in job.artifacts],
            "evidence_ids": list(job.evidence),
        }

    def get_evidence_detail(self, job_id: str, eid: str) -> dict[str, Any]:
        """Fetch audit trail for a verified report claim."""
        job = self.get_job_or_404(job_id)
        item = job.evidence.get(eid)
        if item is None:
            raise HTTPException(status_code=404, detail="Evidence not found")
        return {"id": eid, **item}

    def get_artifact_file(self, job_id: str, name: str) -> tuple[Path, str]:
        """Retrieve artifact path and media type with strict whitelist security."""
        job = self.get_job_or_404(job_id)
        path = job.artifacts.get(name)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return path, self.storage.get_media_type(path)
