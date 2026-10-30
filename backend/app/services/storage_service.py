from __future__ import annotations

import logging
from pathlib import Path
import shutil
from typing import Any

from fastapi import HTTPException, UploadFile

from ..config import Settings

log = logging.getLogger(__name__)

ALLOWED_EXT = {".csv", ".tsv", ".xlsx", ".xls", ".json"}
MEDIA_TYPES = {".png": "image/png", ".csv": "text/csv"}


class StorageService:
    """Service handling file upload validation, sanitization, and workspace file operations."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.max_bytes = settings.max_upload_mb * 1024 * 1024

    @staticmethod
    def sanitize_filename(name: str | None, default_ext: str = ".csv") -> str:
        """Sanitize filename to prevent path traversal and shell injection."""
        base_name = Path(name or "data").name[:120]
        safe = "".join(c for c in base_name if c.isalnum() or c in ("-", "_", ".", " ")).strip()
        return safe or f"data{default_ext}"

    async def process_upload_file(self, file: UploadFile) -> dict[str, Any]:
        """Validate and read an uploaded file into memory within configured size limits."""
        raw_name = Path(file.filename or "data").name[:120]
        ext = Path(raw_name).suffix.lower()

        if ext not in ALLOWED_EXT:
            allowed_str = ", ".join(sorted(ALLOWED_EXT))
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type for '{raw_name}'. Allowed: {allowed_str}",
            )

        content = await file.read(self.max_bytes + 1)
        if not content:
            raise HTTPException(status_code=400, detail=f"File '{raw_name}' is empty")

        if len(content) > self.max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File '{raw_name}' is larger than {self.settings.max_upload_mb}MB",
            )

        safe_name = self.sanitize_filename(raw_name, ext)
        return {"filename": safe_name, "content": content, "ext": ext}

    def copy_file_safe(self, src: Path, dest: Path, mode: int = 0o644) -> None:
        """Safely copy a file and set POSIX permissions for sandbox readability."""
        if src.is_file() and src.stat().st_size > 0:
            shutil.copyfile(src, dest)
            try:
                dest.chmod(mode)
            except OSError:
                pass

    @staticmethod
    def get_media_type(path: Path) -> str:
        """Determine appropriate HTTP MIME type for file response."""
        return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
