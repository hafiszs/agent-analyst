from __future__ import annotations

import json
import logging
from typing import Callable

from ..events import ev
from ..llm import LLM, extract_json
from ..prompts import ADVISOR_SYSTEM
from .base import detect_language, profile_digest
from .state import AgentState

log = logging.getLogger(__name__)


def run_advisor(state: AgentState, llm: LLM, emitter: Callable[[dict], None]) -> dict:
    """Specialist Agent: Advisor / Out-of-Domain Guide.

    Handles general inquiries, system usage questions, and out-of-scope user queries.
    Provides helpful orientation and tailored sample questions based on the dataset profile.
    """
    job = state["job"]
    profile = state.get("profile") or {}
    lang = detect_language(job.query)
    lang_name = "Indonesian" if lang == "id" else "English"

    step_title = "System Guidance & Assistance" if lang == "en" else "Panduan & Tanggapan Sistem"
    emitter(ev("step_started", step="advisor", title=step_title))

    if lang == "en":
        default_report = {
            "title": "System Guidance & Dataset Overview",
            "headline": "Hello! I am your AI Data Analyst, ready to analyze, clean, and visualize your data in an isolated sandbox.",
            "verified_claims": [
                {
                    "text": "Your uploaded dataset has been successfully inspected by the Profiler and is ready for analysis.",
                    "evidence_ids": ["p0"] if "p0" in job.evidence else [],
                    "verified": bool("p0" in job.evidence),
                }
            ],
            "interpretation": [
                "You can ask about spending trends, category distributions, correlations, or automated data cleaning."
            ],
            "recommendations": [
                "Example query: 'Show top 5 categories by total spend'",
                "Example query: 'Clean duplicate rows and parse invalid dates'",
                "Example query: 'Analyze monthly trends and find spending outliers'",
            ],
            "summary": "Your dataset has been profiled and is ready for analytical exploration.",
            "content_markdown": (
                "# System Guidance & Dataset Overview\n\n"
                "Hello! I am your AI Data Analyst, ready to analyze, clean, and visualize your data in an isolated Docker sandbox.\n\n"
                "### Dataset Status\n"
                "Your dataset has been profiled [p0] and is ready for analysis.\n\n"
                "### Suggested Analysis Questions\n"
                "- Show the top 5 categories by total spend\n"
                "- Clean duplicate rows and fix invalid amounts\n"
                "- Generate monthly spending trend charts"
            ),
            "warnings": job.warnings,
        }
    else:
        default_report = {
            "title": "Panduan & Tanggapan Sistem",
            "headline": "Halo! Saya adalah AI Data Analyst yang bertugas menganalisis, membersihkan, dan memvisualisasikan data Anda.",
            "verified_claims": [
                {
                    "text": "File dataset Anda telah berhasil dipelajari oleh Profiler dan siap untuk dianalisis.",
                    "evidence_ids": ["p0"] if "p0" in job.evidence else [],
                    "verified": bool("p0" in job.evidence),
                }
            ],
            "interpretation": [
                "Anda dapat menanyakan hal-hal terkait data seperti tren, perbandingan kategori, korelasi, atau membersihkan data kotor."
            ],
            "recommendations": [
                "Contoh pertanyaan: 'Tampilkan 5 kategori dengan transaksi terbesar'",
                "Contoh pertanyaan: 'Bersihkan baris duplikat dan format tanggal'",
                "Contoh pertanyaan: 'Analisis korelasi antar kolom numerik'",
            ],
            "summary": "File dataset Anda telah berhasil dipelajari dan siap untuk dianalisis.",
            "content_markdown": (
                "# Panduan & Tanggapan Sistem\n\n"
                "Halo! Saya adalah AI Data Analyst yang bertugas menganalisis, membersihkan, dan memvisualisasikan data Anda.\n\n"
                "### Struktur Data\n"
                "File dataset Anda telah berhasil dipelajari oleh Profiler [p0] dan siap untuk dianalisis.\n\n"
                "### Rekomendasi Pertanyaan Analisis\n"
                "- Tampilkan 5 kategori dengan transaksi terbesar\n"
                "- Bersihkan baris duplikat dan format tanggal\n"
                "- Buatkan grafik perbandingan pengeluaran"
            ),
            "warnings": job.warnings,
        }

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
                "PREVIOUS CONVERSATION CONTEXT (Refer to this if the user is asking a follow-up or clarifying a prior answer):\n"
                + "\n".join(history_lines)
                + "\n\n"
            )

    messages = [
        {"role": "system", "content": ADVISOR_SYSTEM},
        {
            "role": "user",
            "content": (
                f"{history_block}"
                f"User query: {job.query}\n"
                f"TARGET LANGUAGE MANDATE: The user's query is in {lang_name}. "
                f"You MUST write the ENTIRE response (title, headline, summary, content_markdown, verified_claims, interpretation, recommendations) in fluent, natural, professional {lang_name}!\n\n"
                f"Dataset profile summary (JSON):\n"
                f"{json.dumps(profile_digest(profile), ensure_ascii=False)}"
            ),
        },
    ]

    try:
        try:
            raw = llm.chat(messages, json_mode=True, temperature=0.3, max_tokens=3000)
        except TypeError:
            raw = llm.chat(messages, json_mode=True)
        data = extract_json(raw)
    except Exception:
        log.exception("advisor LLM call failed; using fallback guidance")
        data = None

    if isinstance(data, dict):
        claims = []
        for c in data.get("verified_claims") or []:
            if isinstance(c, dict):
                ids = [i for i in (c.get("evidence_ids") or []) if i in job.evidence]
                claims.append({
                    "text": str(c.get("text", ""))[:600],
                    "evidence_ids": ids,
                    "verified": bool(ids),
                })
        if not claims:
            claims = default_report["verified_claims"]

        content_md = str(data.get("content_markdown", "")).strip()
        if not content_md:
            md_parts = [f"# {data.get('title', default_report['title'])}\n\n"]
            if data.get("headline"):
                md_parts.append(f"{data.get('headline')}\n\n")
            if data.get("interpretation"):
                md_parts.append("### Informasi & Pembahasan Data\n")
                for item in data.get("interpretation") or []:
                    md_parts.append(f"- {item}\n")
                md_parts.append("\n")
            if data.get("recommendations"):
                md_parts.append("### Rekomendasi Pertanyaan Analisis\n")
                for r in data.get("recommendations") or []:
                    md_parts.append(f"- {r}\n")
            content_md = "".join(md_parts)

        report = {
            "title": str(data.get("title", default_report["title"]))[:200],
            "headline": str(data.get("headline", default_report["headline"]))[:600],
            "summary": str(data.get("summary", data.get("headline", default_report["headline"])))[:1000],
            "content_markdown": content_md,
            "verified_claims": claims,
            "interpretation": [str(x)[:600] for x in (data.get("interpretation") or default_report["interpretation"])][:10],
            "recommendations": [str(x)[:600] for x in (data.get("recommendations") or default_report["recommendations"])][:10],
            "warnings": job.warnings,
        }
    else:
        report = default_report

    job.report = report
    emitter(ev("report_ready", report=report))
    emitter(ev("step_finished", step="advisor", ok=True))

    return {"report": report}
