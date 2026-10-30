from __future__ import annotations

import logging
import shutil
from typing import Callable

from ..config import Settings
from ..events import ev
from ..llm import LLM
from ..prompts import CLEAN_TASK
from ..sandbox import RunResult, safe_file
from .base import MB, StepResult, build_job_context, execute_code_step, load_json, publish_artifact, tail
from .state import AgentState

log = logging.getLogger(__name__)


def check_clean_problem(step: str, res: RunResult) -> tuple[str, str] | None:
    """Validate sandbox execution outcome and required output files for cleaning."""
    if res.reason:
        return res.reason, tail(res.stderr, 800) or f"The run was stopped ({res.reason})."
    if not res.ok:
        return "error", tail(res.stderr, 1500) or f"Exit code {res.exit_code}"
    if safe_file(res.output_dir, "clean.csv", 50 * MB) is None:
        return "missing_output", "/output/clean.csv was not written (or is too large)."
    data = load_json(safe_file(res.output_dir, "changes.json", 1 * MB))
    if not isinstance(data, dict) or not isinstance(data.get("changes"), list):
        return "invalid_output", "/output/changes.json must be a JSON object with rows_before, rows_after and a 'changes' list."
    return None


def run_cleaner(
    state: AgentState,
    llm: LLM,
    sandbox,
    settings: Settings,
    emitter: Callable[[dict], None],
) -> dict:
    """Specialist Agent: Cleaner.

    Generates and executes deterministic cleaning scripts in sandbox with self-healing retries.
    Outputs:
    - /output/clean.csv: Cleaned dataset (copied to /data/clean.csv for subsequent analysis)
    - /output/changes.json: Transformation log used to populate diff and 'c*' evidence entries.
    """
    job = state["job"]
    profile = state.get("profile") or {}
    job_context = build_job_context(job, profile)

    emitter(ev("step_started", step="clean", title="Cleaning data"))

    out = execute_code_step(
        job=job,
        step="clean",
        task=CLEAN_TASK,
        job_context=job_context,
        llm=llm,
        sandbox=sandbox,
        settings=settings,
        emitter=emitter,
        check_problem=check_clean_problem,
    )

    if out.ok:
        res = out.result
        assert res is not None
        clean_path = safe_file(res.output_dir, "clean.csv", 50 * MB)
        assert clean_path is not None
        data_copy = job.data_dir / "clean.csv"
        shutil.copyfile(clean_path, data_copy)
        try:
            data_copy.chmod(0o644)
        except OSError:
            pass
        emitter(publish_artifact(job, clean_path, "clean.csv", "dataset"))

        data = load_json(safe_file(res.output_dir, "changes.json", 1 * MB)) or {}
        changes = [c for c in data.get("changes", []) if isinstance(c, dict)][:50]
        for i, change in enumerate(changes, 1):
            cid = f"c{i}"
            title = f"{str(change.get('action', 'change'))[:120]} ({change.get('column') or 'all rows'})"
            job.evidence[cid] = {
                "kind": "cleaning",
                "title": title,
                "step": "clean",
                "code": out.code,
                "stdout": tail(res.stdout, 4000),
                "data": change,
            }
        emitter(
            ev(
                "diff_ready",
                rows_before=data.get("rows_before"),
                rows_after=data.get("rows_after"),
                changes=[{"id": f"c{i}", **c} for i, c in enumerate(changes, 1)],
            )
        )
    else:
        msg = f"Cleaning failed after {out.attempts} attempts; the next steps used the raw data."
        job.warnings.append(msg)
        emitter(ev("warning", message=msg))

    emitter(ev("step_finished", step="clean", ok=out.ok))

    # Reset reclean flag if cleaner completed
    return {
        "clean_result": out,
        "evidence": job.evidence,
        "warnings": job.warnings,
        "needs_reclean": False,
    }
