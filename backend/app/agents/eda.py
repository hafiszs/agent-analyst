from __future__ import annotations

import logging
from typing import Callable

from ..config import Settings
from ..events import ev
from ..llm import LLM
from ..prompts import EDA_TASK
from ..sandbox import RunResult, safe_file
from .base import MB, SAFE_NAME, StepResult, build_job_context, execute_code_step, load_json, publish_artifact, tail
from .state import AgentState

log = logging.getLogger(__name__)


def check_eda_problem(step: str, res: RunResult) -> tuple[str, str] | None:
    """Validate sandbox execution outcome and required output files for EDA."""
    if res.reason:
        return res.reason, tail(res.stderr, 800) or f"The run was stopped ({res.reason})."
    if not res.ok:
        return "error", tail(res.stderr, 1500) or f"Exit code {res.exit_code}"
    data = load_json(safe_file(res.output_dir, "results.json", 1 * MB))
    if not isinstance(data, list) or not data:
        return "invalid_output", "/output/results.json must be a non-empty JSON list of findings."
    return None


def run_eda(
    state: AgentState,
    llm: LLM,
    sandbox,
    settings: Settings,
    emitter: Callable[[dict], None],
) -> dict:
    """Specialist Agent: EDA (Exploratory Data Analysis).

    Generates analytical code and visualizations (matplotlib charts) inside sandbox.
    Outputs:
    - /output/results.json: Structured findings and statistics.
    - /output/*.png: Visual charts linked to findings.
    - Anomaly detection: Inspects findings to determine if unaddressed data dirtiness
      warrants looping back to the Cleaner agent.
    """
    job = state["job"]
    profile = state.get("profile") or {}
    job_context = build_job_context(job, profile)
    reclean_count = state.get("reclean_count", 0)
    needs_reclean = False

    emitter(ev("step_started", step="eda", title="Exploratory analysis"))

    out = execute_code_step(
        job=job,
        step="eda",
        task=EDA_TASK,
        job_context=job_context,
        llm=llm,
        sandbox=sandbox,
        settings=settings,
        emitter=emitter,
        check_problem=check_eda_problem,
    )

    if out.ok:
        res = out.result
        assert res is not None
        findings = [f for f in (load_json(safe_file(res.output_dir, "results.json", 1 * MB)) or []) if isinstance(f, dict)][:8]
        for i, f in enumerate(findings, 1):
            fid = f"f{i}"
            chart_name = None
            chart = f.get("chart")
            if isinstance(chart, str) and SAFE_NAME.match(chart) and chart.lower().endswith(".png"):
                src = safe_file(res.output_dir, chart, 5 * MB)
                if src is not None:
                    emitter(publish_artifact(job, src, chart, "chart"))
                    chart_name = chart
            entry = {
                "id": fid,
                "title": str(f.get("title", ""))[:200],
                "statement": str(f.get("statement", ""))[:600],
                "evidence": f.get("evidence"),
                "chart": chart_name,
            }
            job.evidence[fid] = {
                "kind": "finding",
                "title": entry["title"],
                "step": "eda",
                "code": out.code,
                "stdout": tail(res.stdout, 4000),
                "data": entry,
            }
            emitter(ev("finding", **entry))

            # Check if findings signal data quality issues requiring loop-back to clean
            if bool(f.get("needs_reclean")) or bool(f.get("data_corrupted")):
                needs_reclean = True

        if needs_reclean and reclean_count < 1:
            msg = "EDA detected unhandled data anomalies; requesting cleaner re-pass."
            job.warnings.append(msg)
            emitter(ev("warning", message=msg))
    else:
        msg = f"Analysis failed after {out.attempts} attempts; the report only covers what succeeded."
        job.warnings.append(msg)
        emitter(ev("warning", message=msg))

    emitter(ev("step_finished", step="eda", ok=out.ok))

    return {
        "eda_result": out,
        "evidence": job.evidence,
        "warnings": job.warnings,
        "needs_reclean": needs_reclean and (reclean_count < 1),
    }
