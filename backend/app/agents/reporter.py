from __future__ import annotations

import json
import logging
from typing import Callable

from ..events import ev
from ..llm import LLM, extract_json
from ..prompts import REPORT_SYSTEM
from .base import detect_language
from .state import AgentState

log = logging.getLogger(__name__)


def fallback_report(job, lang: str = "en") -> dict:
    """Deterministic fallback report when LLM synthesis fails."""
    claims = [
        {"text": v["data"].get("statement", v["title"]), "evidence_ids": [k], "verified": True}
        for k, v in job.evidence.items()
        if v["kind"] == "finding"
    ]
    if lang == "id":
        md_lines = ["# Laporan Analisis Data\n\nRingkasan temuan analisis data dari dataset yang diunggah:\n\n"]
        for c in claims:
            md_lines.append(f"- {c['text']} [{c['evidence_ids'][0]}]\n")
        return {
            "title": "Laporan Analisis Data",
            "headline": "Ringkasan naratif tidak dapat dibuat otomatis; temuan terverifikasi dicantumkan di bawah ini.",
            "summary": "Ringkasan naratif tidak dapat dibuat otomatis; temuan terverifikasi dicantumkan di bawah ini.",
            "content_markdown": "".join(md_lines),
            "verified_claims": claims,
            "interpretation": [],
            "recommendations": [],
            "warnings": job.warnings,
        }
    else:
        md_lines = ["# Data Analysis Report\n\nSummary of verified findings from the uploaded dataset:\n\n"]
        for c in claims:
            md_lines.append(f"- {c['text']} [{c['evidence_ids'][0]}]\n")
        return {
            "title": "Data Analysis Report",
            "headline": "The narrative summary could not be synthesized; verified findings are listed below.",
            "summary": "The narrative summary could not be synthesized; verified findings are listed below.",
            "content_markdown": "".join(md_lines),
            "verified_claims": claims,
            "interpretation": [],
            "recommendations": [],
            "warnings": job.warnings,
        }


def run_reporter(state: AgentState, llm: LLM, emitter: Callable[[dict], None]) -> dict:
    """Specialist Agent: Reporter.

    Synthesizes all collected sandbox evidence ('p0', 'c*', 'f*') into an executive
    analytical report with verified citations. Ensures any claim lacking valid evidence IDs
    is marked verified=False.
    """
    job = state["job"]
    lang = detect_language(job.query)
    lang_name = "Indonesian" if lang == "id" else "English"

    step_title = "Writing executive report" if lang == "en" else "Menyusun Laporan Eksekutif"
    emitter(ev("step_started", step="report", title=step_title))
    emitter(
        ev(
            "evidence_index",
            items=[{"id": k, "kind": v["kind"], "title": v["title"]} for k, v in job.evidence.items()],
        )
    )

    digest = json.dumps(
        [{"id": k, "kind": v["kind"], "data": v["data"]} for k, v in job.evidence.items()],
        ensure_ascii=False,
    )[:30000]
    plan = job.plan or {}
    available_charts = [
        {"name": name, "url": f"/api/jobs/{job.id}/files/{name}"}
        for name in sorted(job.artifacts.keys())
        if name.endswith(".png")
    ]

    history_block = ""
    history = getattr(job, "history", None)
    if history:
        history_lines = []
        for turn in history[-6:]:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "").strip()
            if content:
                history_lines.append(f"- {role}: {content}")
        if history_lines:
            history_block = (
                "PREVIOUS CONVERSATION CONTEXT (Tie your report narrative and executive recommendations seamlessly into this ongoing discussion):\n"
                + "\n".join(history_lines)
                + "\n\n"
            )

    messages = [
        {"role": "system", "content": REPORT_SYSTEM},
        {
            "role": "user",
            "content": (
                f"{history_block}"
                f"User request: {job.query}\n"
                f"MANDATORY LANGUAGE DIRECTIVE: The user's query is in {lang_name}. "
                f"You MUST write the ENTIRE report (title, headline, summary, content_markdown, verified_claims, interpretation, recommendations) strictly in {lang_name}!\n"
                f"(Keep embedded chart image tags like ![Chart](chart_1.png) and Python code in English, but all narrative text, explanations, headings, and table headers must be in {lang_name}).\n\n"
                f"Plan: {json.dumps(plan.get('plan', []), ensure_ascii=False)}\n\n"
                f"Available Generated Charts to embed in content_markdown:\n{json.dumps(available_charts, indent=2)}\n\n"
                f"EVIDENCE (JSON list of verified facts from isolated sandbox):\n{digest}"
            ),
        },
    ]

    try:
        try:
            raw = llm.chat(messages, json_mode=True, temperature=0.35, max_tokens=8192)
        except TypeError:
            raw = llm.chat(messages, json_mode=True)
        data = extract_json(raw)
        if not data:
            log.warning("extract_json returned None on report raw reply. Length: %d. Snippet: %s", len(raw or ""), (raw or "")[:300])
    except Exception:
        log.exception("report call failed; using the fallback report")
        data = None

    if not isinstance(data, dict):
        report = fallback_report(job, lang=lang)
    else:
        claims = []
        for c in data.get("verified_claims") or []:
            if not isinstance(c, dict):
                continue
            ids = [i for i in (c.get("evidence_ids") or []) if isinstance(i, str) and i in job.evidence]
            claims.append({"text": str(c.get("text", ""))[:600], "evidence_ids": ids, "verified": bool(ids)})

        content_md = str(data.get("content_markdown", "")).strip()
        if not content_md:
            default_title = "Data Analysis Report" if lang == "en" else "Laporan Analisis Data"
            md_parts = [f"# {data.get('title', default_title)}\n"]
            if data.get("headline"):
                md_parts.append(f"{data.get('headline')}\n")
            if claims:
                claims_hdr = "\n### Key Verified Findings\n" if lang == "en" else "\n### Temuan Utama Terverifikasi\n"
                md_parts.append(claims_hdr)
                for c in claims:
                    cite_tag = f" [{' '.join(c['evidence_ids'])}]" if c["evidence_ids"] else ""
                    md_parts.append(f"- {c['text']}{cite_tag}\n")
            if data.get("interpretation"):
                interp_hdr = "\n### Strategic Interpretation\n" if lang == "en" else "\n### Analisis & Pembahasan\n"
                md_parts.append(interp_hdr)
                for item in data.get("interpretation") or []:
                    md_parts.append(f"- {item}\n")
            if data.get("recommendations"):
                rec_hdr = "\n### Business Recommendations\n" if lang == "en" else "\n### Rekomendasi Bisnis\n"
                md_parts.append(rec_hdr)
                for r in data.get("recommendations") or []:
                    md_parts.append(f"- {r}\n")
            content_md = "\n".join(md_parts)

        report = {
            "title": str(data.get("title", "Data Analysis Report" if lang == "en" else "Laporan Analisis Data"))[:200],
            "headline": str(data.get("headline", ""))[:600],
            "summary": str(data.get("summary", data.get("headline", "")))[:1000],
            "content_markdown": content_md,
            "verified_claims": claims,
            "interpretation": [str(x)[:600] for x in (data.get("interpretation") or [])][:10],
            "recommendations": [str(x)[:600] for x in (data.get("recommendations") or [])][:10],
            "warnings": job.warnings,
        }

    job.report = report
    emitter(ev("report_ready", report=report))
    emitter(ev("step_finished", step="report", ok=True))

    return {"report": report}
