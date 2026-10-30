from __future__ import annotations

import json
import logging
from typing import Callable

from ..events import ev
from ..llm import LLM, extract_json
from ..prompts import PLAN_SYSTEM
from .base import INTENTS, detect_language, profile_digest
from .state import AgentState

log = logging.getLogger(__name__)


def run_planner(state: AgentState, llm: LLM, emitter: Callable[[dict], None]) -> dict:
    """Specialist Agent: Planner.

    Analyzes user intent and data profile using LLM to dynamically determine:
    1. Pipeline steps needed (e.g. ['clean', 'eda', 'report'], ['eda', 'report'], etc.)
    2. Ordered plan checklist items
    3. Analytical intent ('full_analysis', 'clean_only', 'focused_analysis', 'find_issues')
    """
    job = state["job"]
    profile = state.get("profile") or {}
    lang = detect_language(job.query)
    lang_name = "Indonesian" if lang == "id" else "English"

    full_plan = (
        ["Bersihkan data", "Analisis data dengan visualisasi", "Susun laporan eksekutif"]
        if lang == "id"
        else ["Clean the data", "Analyze data with visualizations", "Write executive report"]
    )
    full = {
        "intent": "full_analysis",
        "steps": ["clean", "eda", "report"],
        "plan": full_plan,
        "reason": "Rencana default analisis menyeluruh" if lang == "id" else "Default comprehensive analysis plan",
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
                "PREVIOUS CONVERSATION CONTEXT (Take this into account if the user's request is a follow-up or refinement):\n"
                + "\n".join(history_lines)
                + "\n\n"
            )

    try:
        raw = llm.chat(
            [
                {"role": "system", "content": PLAN_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"{history_block}"
                        f"User request: {job.query}\n"
                        f"MANDATORY LANGUAGE DIRECTIVE: The user's query is in {lang_name}. "
                        f"You MUST write 'plan' and 'reason' strictly in {lang_name}!\n\n"
                        f"Dataset profile (JSON):\n"
                        f"{json.dumps(profile_digest(profile), ensure_ascii=False)}"
                    ),
                },
            ],
            json_mode=True,
        )
    except Exception:
        log.exception("planner call failed; using the default plan")
        plan = full
    else:
        data = extract_json(raw)
        if not isinstance(data, dict) or not data.get("steps"):
            plan = full
        else:
            wanted = data.get("steps") or []
            intent = data.get("intent") if data.get("intent") in INTENTS else "full_analysis"
            if intent == "general_inquiry" or "advisor" in wanted:
                steps = ["advisor"]
            else:
                steps = [x for x in ("clean", "eda") if x in wanted] + ["report"]
            plan_items = [str(x)[:200] for x in (data.get("plan") or [])][:8] or full["plan"]
            plan = {
                "intent": intent,
                "steps": steps,
                "plan": plan_items,
                "reason": str(data.get("reason", ""))[:300],
            }

    job.plan = plan
    emitter(ev("plan_ready", **plan))
    return {"plan": plan}
