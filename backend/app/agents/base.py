from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..config import Settings
from ..events import ev
from ..jobs import Job
from ..llm import LLM, extract_code
from ..prompts import code_system, feedback_message
from ..sandbox import RunResult

log = logging.getLogger(__name__)

SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
MB = 1024 * 1024
INTENTS = {"clean_only", "find_issues", "focused_analysis", "full_analysis", "general_inquiry"}

_ID_WORDS = {
    "apakah", "bisa", "bantu", "tolong", "analisis", "analisa", "data", "ini", "itu",
    "yang", "dan", "di", "dari", "ke", "untuk", "unutk", "dengan", "saya", "tampilkan",
    "buatkan", "grafik", "bagaimana", "berapa", "kategori", "pengeluaran", "penjualan",
    "gaji", "karyawan", "transaksi", "bersihkan", "perbaiki", "ada", "apa", "kenapa",
    "mengapa", "siapa", "dimana", "kapan", "ringkasan", "laporan", "tren", "korelasi",
    "duplikat", "baris", "kolom", "terbesar", "terkecil", "terbanyak", "tertinggi",
    "terendah", "total", "rata", "rata-rata", "jumlah", "bulan", "tahun", "halo", "hai",
    "tolong", "bagus", "kurang", "semua", "seluruh", "hitung", "lihat", "tabel", "jelaskan",
    "maksud", "arti", "makna", "menganalisis", "membersihkan", "membuat", "tentang", "ya",
    "anda", "kamu", "tersebut", "kita", "coba", "paling", "tinggi", "rendah"
}

_EN_WORDS = {
    "what", "why", "how", "who", "when", "where", "which", "is", "are", "can", "could",
    "would", "should", "will", "please", "help", "me", "analyze", "analysis", "clean",
    "cleaning", "show", "give", "display", "plot", "chart", "graph", "spend", "spending",
    "top", "bottom", "largest", "smallest", "highest", "lowest", "trend", "trends",
    "correlation", "duplicate", "duplicates", "row", "rows", "column", "columns", "the",
    "a", "an", "of", "in", "to", "for", "with", "on", "at", "by", "from", "and", "or",
    "not", "this", "that", "these", "those", "dataset", "table", "summary", "report",
    "explain", "overview", "hello", "hi", "hey", "find", "check", "inspect", "audit",
    "you", "your", "give", "tell", "describe", "breakdown", "break", "down"
}


def detect_language(query: str) -> str:
    """Detect whether query is Indonesian ('id') or English ('en').

    Checks explicit user language requests first, then scores vocabulary against known tokens.
    Defaults to 'id' if Indonesian tokens dominate or if user query is in Indonesian,
    and 'en' if English tokens dominate or no Indonesian signals are present.
    """
    q = (query or "").lower().strip()
    if not q:
        return "en"

    # Explicit directives
    if re.search(r"\b(in\s+english|use\s+english|speak\s+english|english\s+please|bahasa\s+inggris)\b", q):
        return "en"
    if re.search(r"\b(dalam\s+bahasa\s+indonesia|pakai\s+bahasa\s+indonesia|bahasa\s+indo|bahasa\s+indonesia|in\s+indonesian)\b", q):
        return "id"

    id_count = 0
    en_count = 0
    words = re.findall(r"[a-z]+", q)
    for w in words:
        if w in _ID_WORDS:
            id_count += 1
        if w in _EN_WORDS:
            en_count += 1

    if id_count > en_count:
        return "id"
    if en_count > id_count:
        return "en"
    if any(w in _ID_WORDS for w in words):
        return "id"
    return "en"



def tail(text: str, n: int = 1500) -> str:
    """Return the last n characters of text with an ellipsis prefix if truncated."""
    text = text or ""
    return text if len(text) <= n else "…" + text[-n:]


def last_json_line(text: str) -> dict | None:
    """Extract and parse the last valid JSON dictionary line from multi-line text."""
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
    return None


def load_json(path: Path | None):
    """Safely read and parse a JSON file from disk."""
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def profile_digest(profile: dict) -> dict:
    """Produce a concise dictionary summarizing dataset profile for LLM context, including column sample values and multi-file details."""
    if profile.get("multi_file") and profile.get("file_profiles"):
        return {
            "multi_file": True,
            "total_files": profile.get("total_files"),
            "files": [
                {
                    "file": fp.get("file"),
                    "rows": fp.get("rows"),
                    "columns_total": fp.get("columns_total"),
                    "duplicate_rows": fp.get("duplicate_rows"),
                    "columns": [
                        {k: c.get(k) for k in ("name", "dtype", "nulls", "unique", "unique_after_normalizing", "samples") if k in c}
                        for c in fp.get("columns", [])
                    ],
                }
                for fp in profile.get("file_profiles", [])
            ],
        }
    return {
        "rows": profile.get("rows"),
        "columns_total": profile.get("columns_total"),
        "duplicate_rows": profile.get("duplicate_rows"),
        "columns": [
            {k: c.get(k) for k in ("name", "dtype", "nulls", "unique", "unique_after_normalizing", "samples") if k in c}
            for c in profile.get("columns", [])
        ],
    }


def publish_artifact(job: Job, src: Path, name: str, kind: str) -> dict:
    """Copy an output file into the job's public artifacts directory and record event."""
    dest = job.artifacts_dir / name
    shutil.copyfile(src, dest)
    job.artifacts[name] = dest
    return ev("artifact", name=name, kind=kind, url=f"/api/jobs/{job.id}/files/{name}", size=dest.stat().st_size)


def build_job_context(job: Job, profile: dict) -> str:
    """Construct read-only filesystem and schema context for code generation prompts."""
    files = sorted(p.name for p in job.data_dir.iterdir() if p.is_file())
    multi_file_note = ""
    if profile.get("multi_file") or len(files) > 1:
        multi_file_note = (
            "\nNOTE: Multiple datasets are provided in /data. You can read, compare, merge, or join them "
            "using pandas (e.g. pd.read_csv('/data/filename.csv')).\n"
        )

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
                "\nPREVIOUS CONVERSATION CONTEXT (Reference this for follow-up context, entity names, or prior findings):\n"
                + "\n".join(history_lines)
                + "\n"
            )

    return (
        f"User request: {job.query}\n"
        f"{history_block}"
        f"Files in /data (read-only): {', '.join(files)}{multi_file_note}\n"
        f"How the file was loaded during profiling: {profile.get('loaded_with')}\n"
        f"Dataset profile (JSON): {json.dumps(profile, ensure_ascii=False)[:12000]}"
    )


@dataclass
class StepResult:
    """Outcome of a self-healing code execution step."""
    ok: bool
    code: str = ""
    result: RunResult | None = None
    attempts: int = 0


def execute_code_step(
    job: Job,
    step: str,
    task: str,
    job_context: str,
    llm: LLM,
    sandbox,
    settings: Settings,
    emitter: Callable[[dict], None],
    check_problem: Callable[[str, RunResult], tuple[str, str] | None],
) -> StepResult:
    """Execute a self-healing LLM-sandbox code generation loop.

    Flow per attempt:
    1. Emit attempt_started
    2. Prompt LLM for Python script
    3. Extract code from markdown fences
    4. Execute script in isolated sandbox, streaming intermediate events to emitter
    5. Validate output artifacts; if clean, return success
    6. If error/invalid output, format error into prompt feedback and retry up to max_retries
    """
    s = settings
    messages = [
        {"role": "system", "content": code_system(s)},
        {"role": "user", "content": f"{task}\n\n{job_context}"},
    ]
    last: StepResult = StepResult(ok=False)
    for attempt in range(1, s.max_retries + 1):
        emitter(ev("attempt_started", step=step, attempt=attempt, max_attempts=s.max_retries))
        try:
            raw = llm.chat(messages, temperature=0.1, max_tokens=7000)
        except TypeError:
            raw = llm.chat(messages)
        except Exception as e:
            log.warning("LLM generation failed on attempt %d: %s", attempt, e)
            raw = ""
        code = extract_code(raw)

        if not code:
            problem = ("no_code", "No python code block found in the reply.")
            last = StepResult(ok=False, attempts=attempt)
        else:
            emitter(ev("code_generated", step=step, attempt=attempt, code=code))
            gen = sandbox.run(
                script=code,
                data_dir=job.data_dir,
                run_dir=job.dir / "runs" / f"{step}_{attempt}",
                step=step,
                attempt=attempt,
            )
            # Drain sandbox generator, yielding events to emitter and capturing RunResult
            try:
                while True:
                    box_ev = next(gen)
                    emitter(box_ev)
            except StopIteration as stop:
                res = stop.value

            problem = check_problem(step, res)
            last = StepResult(ok=problem is None, code=code, result=res, attempts=attempt)
            if problem is None:
                emitter(ev("attempt_succeeded", step=step, attempt=attempt))
                return last

        reason, message = problem
        emitter(
            ev(
                "attempt_failed",
                step=step,
                attempt=attempt,
                reason=reason,
                error=tail(message, 1500),
                will_retry=attempt < s.max_retries,
            )
        )
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": feedback_message(reason, tail(message, 1500), s)},
        ]

    emitter(ev("step_failed", step=step, attempts=s.max_retries))
    return last
