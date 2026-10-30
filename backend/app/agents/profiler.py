from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from ..events import ev
from .base import last_json_line, profile_digest, tail
from .state import AgentState

log = logging.getLogger(__name__)

PROFILE_SCRIPT = (Path(__file__).parent.parent / "sandbox_scripts" / "profile.py").read_text(encoding="utf-8")


def run_profiler(state: AgentState, sandbox, emitter: Callable[[dict], None]) -> dict:
    """Specialist Agent: Profiler.

    Executes a deterministic profiling script inside the sandbox to discover
    column data types, null counts, duplicate rows, and normalization samples.
    Registers 'p0' in evidence registry upon success.
    """
    job = state["job"]
    emitter(ev("step_started", step="profile", title="Profiling data"))

    gen = sandbox.run(
        script=PROFILE_SCRIPT,
        data_dir=job.data_dir,
        run_dir=job.dir / "runs" / "profile",
        step="profile",
        attempt=1,
    )
    try:
        while True:
            emitter(next(gen))
    except StopIteration as stop:
        res = stop.value

    profile = last_json_line(res.stdout) if res.ok else None
    if profile is None:
        emitter(ev("job_failed", error="Could not read the uploaded file", detail=tail(res.stderr, 800)))
        return {"error": "Could not read the uploaded file", "profile": None}

    job.evidence["p0"] = {
        "kind": "profile",
        "title": "Data profile",
        "step": "profile",
        "code": PROFILE_SCRIPT,
        "stdout": tail(res.stdout, 3000),
        "data": profile_digest(profile),
    }
    emitter(ev("profile_ready", profile=profile))
    emitter(ev("step_finished", step="profile", ok=True))

    return {"profile": profile, "evidence": job.evidence}
