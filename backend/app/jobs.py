"""Job state + background runner. Events are buffered per job so the SSE endpoint can replay and reconnect."""
from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

from .config import Settings
from .events import ev

log = logging.getLogger(__name__)


class Job:
    """Represents a single data analysis task.

    Manages the isolated workspace directories on disk (read-only /data and writable /artifacts),
    maintains thread-safe execution status, and buffers lifecycle events for real-time SSE streaming.
    """

    def __init__(
        self,
        job_id: str,
        root: Path,
        query: str,
        filename: str,
        raw_name: str,
        filenames: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ):
        """Initialize a new Job instance.

        Args:
            job_id: Unique 12-character hex identifier.
            root: Root path for jobs storage (/srv/agent-work/jobs).
            query: Natural language prompt or question from the user.
            filename: Original user filename for display in UI.
            raw_name: Normalized filename on disk (e.g. 'raw.csv') read by sandbox.
            filenames: Optional list of all uploaded filenames for multi-dataset analysis.
            history: Optional list of prior conversation turns for follow-up context.
        """
        self.id = job_id
        self.dir = root / job_id
        self.data_dir = self.dir / "data"  # mounted read-only into every sandbox run
        self.artifacts_dir = self.dir / "artifacts"  # files the API may serve
        self.query = query
        self.filenames = filenames or [filename]
        self.filename = ", ".join(self.filenames) if len(self.filenames) > 1 else filename
        self.raw_name = raw_name
        self.history = list(history or [])
        self.created = time.time()
        self.status = "queued"  # queued | running | done | failed
        self.events: list[dict] = []
        self.cond = threading.Condition()
        self.done = False
        # filled in by the agent
        self.plan: dict | None = None
        self.report: dict | None = None
        self.evidence: dict[str, dict] = {}
        self.artifacts: dict[str, Path] = {}
        self.warnings: list[str] = []

    def add(self, event: dict) -> None:
        """Append an event to history and wake up SSE listener threads.

        Thread-safe: acquires self.cond lock, appends event to buffer,
        and triggers notify_all() to awaken any sleeping iter_events generator.
        """
        with self.cond:
            self.events.append(event)
            self.cond.notify_all()

    def finish(self) -> None:
        """Mark the job as completed or failed and notify all listeners.

        Inspects the final event type to determine if the run was 'done' or 'failed',
        sets done=True, and wakes up iter_events threads for graceful shutdown.
        """
        with self.cond:
            last = self.events[-1]["type"] if self.events else None
            self.status = "done" if last == "job_done" else "failed"
            self.done = True
            self.cond.notify_all()

    def iter_events(self, start: int = 0) -> Iterator[tuple[int, dict] | None]:
        """Generator yielding (index, event) to the SSE streaming endpoint.

        Features:
        - Replay & resume: starts streaming from 'start' index (supports Last-Event-ID).
        - Non-busy waiting: sleeps on self.cond.wait() until add() or finish() triggers notify_all().
        - Keep-alive heartbeat: yields None every 10 seconds if idle to prevent proxy timeout.
        - Graceful exit: returns cleanly once all events are flushed and job.done is True.
        """
        i = start
        while True:
            with self.cond:
                if i >= len(self.events) and not self.done:
                    self.cond.wait(timeout=10)
                batch = self.events[i:]
                finished = self.done
            if batch:
                for event in batch:
                    yield i, event
                    i += 1
            elif finished:
                return
            else:
                yield None


class JobManager:
    """Central manager for job lifecycles, concurrency limits, and background execution.

    Coordinates:
    - Concurrency control via BoundedSemaphore (limits simultaneous Docker sandboxes).
    - Asynchronous background worker threads for Agent orchestrations.
    - Automatic cleanup (purge) of expired job files and memory entries after TTL.
    """

    def __init__(self, settings: Settings, agent):
        """Initialize the JobManager.

        Args:
            settings: Application configuration settings.
            agent: The AI Agent orchestrator instance.
        """
        self.s = settings
        self.agent = agent
        self.root = Path(settings.work_dir) / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(settings.max_concurrent_jobs)

    def get(self, job_id: str) -> Job | None:
        """Lookup an active or buffered Job by its ID."""
        return self.jobs.get(job_id)

    def create(
        self,
        *,
        query: str,
        filename: str | None = None,
        content: bytes | None = None,
        ext: str | None = None,
        files: list[dict] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> Job:
        """Create a new job, write initial dataset files to disk, and launch worker thread.

        Supports either single file parameters (filename, content, ext) or multiple files
        via `files=[{"filename": str, "content": bytes, "ext": str}, ...]`.

        Steps:
        1. Purges expired jobs to free up disk and memory.
        2. Normalizes dataset files and creates directory layout.
        3. Sets chmod permissions (0755/0644) so non-root Docker sandbox (UID 1000) can read /data.
        4. Registers job in self.jobs dictionary with thread-safe lock.
        5. Spawns background daemon thread running _run(job) and immediately returns.
        """
        self.purge()

        file_list: list[dict] = []
        if files:
            file_list = [f for f in files if f.get("content")]
        elif filename and content is not None:
            file_list = [{"filename": filename, "content": content, "ext": ext or Path(filename).suffix.lower()}]

        if not file_list:
            raise ValueError("No valid files provided for job creation")

        primary = file_list[0]
        filenames = [f["filename"] for f in file_list]
        primary_ext = primary.get("ext") or Path(primary["filename"]).suffix.lower() or ".csv"
        display_name = ", ".join(filenames) if len(filenames) > 1 else primary["filename"]
        raw_name = f"raw{primary_ext}"

        job = Job(
            uuid.uuid4().hex[:12],
            self.root,
            query,
            display_name,
            raw_name,
            filenames=filenames,
            history=history,
        )
        job.data_dir.mkdir(parents=True)
        job.artifacts_dir.mkdir(parents=True)
        os.chmod(job.data_dir, 0o755)

        # Write each uploaded file with sanitized original name
        for item in file_list:
            fname = Path(item["filename"]).name
            safe_fname = "".join(c for c in fname if c.isalnum() or c in ("-", "_", ".", " ")).strip() or f"data{primary_ext}"
            file_path = job.data_dir / safe_fname
            file_path.write_bytes(item["content"])
            os.chmod(file_path, 0o644)

        # Backward compatibility: ensure raw{primary_ext} exists for any legacy script expecting it
        raw = job.data_dir / job.raw_name
        if not raw.exists():
            raw.write_bytes(primary["content"])
            os.chmod(raw, 0o644)

        with self._lock:
            self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def _run(self, job: Job) -> None:
        """Background worker thread executing the AI analysis pipeline.

        Flow:
        1. Acquires semaphore slot (emits 'queued' event and blocks if capacity is full).
        2. Sets job status to 'running' and streams each event yielded by agent.run(job).
        3. Catches unexpected exceptions with safety-net and records 'job_failed'.
        4. In finally block, releases semaphore slot and calls job.finish().
        """
        if not self._slots.acquire(blocking=False):
            job.add(ev("queued", message="Waiting for a free sandbox slot"))
            self._slots.acquire()
        try:
            job.status = "running"
            for event in self.agent.run(job):
                job.add(event)
        except Exception as exc:  # the agent handles expected errors itself; this is the safety net
            log.exception("job %s crashed", job.id)
            job.add(ev("job_failed", error="Internal error", detail=type(exc).__name__))
        finally:
            self._slots.release()
            job.finish()

    def purge(self) -> None:
        """Garbage collector: delete finished jobs older than TTL from disk and memory."""
        now = time.time()
        with self._lock:
            old = [j for j in self.jobs.values() if j.done and now - j.created > self.s.job_ttl_s]
            for j in old:
                shutil.rmtree(j.dir, ignore_errors=True)
                self.jobs.pop(j.id, None)
