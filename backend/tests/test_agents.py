import json
from pathlib import Path

from app.agents import (
    AgentState,
    run_advisor,
    run_cleaner,
    run_eda,
    run_planner,
    run_profiler,
    run_reporter,
)
from app.graph import create_agent_graph, route_after_eda, route_after_planner
from app.jobs import Job


class DummyLLM:
    def chat(self, messages, json_mode=False):
        sys = messages[0]["content"]
        if "planner" in sys:
            return json.dumps({
                "intent": "full_analysis",
                "steps": ["clean", "eda", "report"],
                "plan": ["Clean data", "Explore", "Report"],
                "reason": "Comprehensive review",
            })
        if "Advisor" in sys:
            return json.dumps({
                "title": "Advisor Guidance",
                "headline": "I am your AI Data Analyst",
                "verified_claims": [{"text": "You can ask about data", "evidence_ids": ["p0"]}],
                "interpretation": ["Capabilities"],
                "recommendations": ["Try asking about spending"],
            })
        if "writing a report" in sys or "report" in sys:
            return json.dumps({
                "title": "Specialist Report",
                "headline": "Synthesis complete",
                "verified_claims": [{"text": "Claim 1", "evidence_ids": ["f1"]}],
                "interpretation": ["Insight"],
                "recommendations": ["Action"],
            })
        return "```python\nprint('hello')\n```"


def test_routing_logic():
    # Planner routing
    assert route_after_planner({"plan": {"steps": ["clean", "eda", "report"]}}) == "cleaner"
    assert route_after_planner({"plan": {"steps": ["eda", "report"]}}) == "eda"
    assert route_after_planner({"plan": {"steps": ["report"]}}) == "reporter"
    assert route_after_planner({"plan": {"intent": "general_inquiry", "steps": ["advisor"]}}) == "advisor"
    assert route_after_planner({"plan": {"steps": ["advisor"]}}) == "advisor"

    # EDA loop-back routing
    assert route_after_eda({"needs_reclean": True, "reclean_count": 0}) == "cleaner"
    assert route_after_eda({"needs_reclean": True, "reclean_count": 1}) == "reporter"
    assert route_after_eda({"needs_reclean": False, "reclean_count": 0}) == "reporter"


def test_planner_specialist(tmp_path):
    job = Job("job1", tmp_path, "Clean and analyze", "test.csv", "raw.csv")
    state: AgentState = {
        "job": job,
        "profile": {"rows": 100, "columns_total": 5, "columns": []},
    }
    events = []
    res = run_planner(state, DummyLLM(), events.append)

    assert res["plan"]["intent"] == "full_analysis"
    assert "clean" in res["plan"]["steps"]
    assert len(events) == 1
    assert events[0]["type"] == "plan_ready"


def test_reporter_specialist(tmp_path):
    job = Job("job2", tmp_path, "Report please", "test.csv", "raw.csv")
    job.evidence["f1"] = {
        "kind": "finding",
        "title": "Finding 1",
        "step": "eda",
        "code": "print(1)",
        "stdout": "1",
        "data": {"statement": "Insight 1"},
    }
    state: AgentState = {
        "job": job,
        "evidence": job.evidence,
        "warnings": [],
    }
    events = []
    res = run_reporter(state, DummyLLM(), events.append)

    assert res["report"]["title"] == "Specialist Report"
    assert res["report"]["verified_claims"][0]["verified"] is True
    event_types = [e["type"] for e in events]
    assert "step_started" in event_types
    assert "evidence_index" in event_types
    assert "report_ready" in event_types
    assert "step_finished" in event_types


def test_advisor_specialist(tmp_path):
    job = Job("job3", tmp_path, "Who is the president?", "test.csv", "raw.csv")
    job.evidence["p0"] = {
        "kind": "profile",
        "title": "Data profile",
        "step": "profile",
        "code": "profile",
        "stdout": "profile",
        "data": {},
    }
    state: AgentState = {
        "job": job,
        "profile": {"rows": 50, "columns_total": 3, "columns": []},
        "evidence": job.evidence,
        "warnings": [],
    }
    events = []
    res = run_advisor(state, DummyLLM(), events.append)

    assert res["report"]["title"] == "Advisor Guidance"
    assert res["report"]["headline"] == "I am your AI Data Analyst"
    event_types = [e["type"] for e in events]
    assert "step_started" in event_types
    assert "report_ready" in event_types
    assert "step_finished" in event_types


def test_missing_column_query_handling(tmp_path):
    class MissingColumnLLM:
        def chat(self, messages, json_mode=False):
            sys = messages[0]["content"]
            if "planner" in sys:
                return json.dumps({
                    "intent": "general_inquiry",
                    "steps": ["advisor"],
                    "plan": ["Inform user that column 'gaji' is missing"],
                    "reason": "Requested column 'gaji' does not exist in dataset",
                })
            return json.dumps({
                "title": "Pemberitahuan Kolom Tidak Ditemukan",
                "headline": "Kolom 'gaji' tidak ditemukan pada dataset.",
                "verified_claims": [{"text": "Kolom yang ada adalah: produk, harga, stok.", "evidence_ids": ["p0"]}],
                "interpretation": ["Dataset ini berisi inventori barang, bukan data penggajian."],
                "recommendations": ["Coba tanyakan: 'Berapa total nilai stok per produk?'"],
            })

    job = Job("job4", tmp_path, "Tampilkan rata-rata gaji karyawan", "inventori.csv", "raw.csv")
    job.evidence["p0"] = {
        "kind": "profile",
        "title": "Data profile",
        "step": "profile",
        "code": "profile",
        "stdout": "profile",
        "data": {},
    }
    state: AgentState = {
        "job": job,
        "profile": {"rows": 20, "columns_total": 3, "columns": [{"name": "produk"}, {"name": "harga"}, {"name": "stok"}]},
        "evidence": job.evidence,
        "warnings": [],
    }

    # 1. Planner identifies missing column and routes to advisor
    events = []
    plan_res = run_planner(state, MissingColumnLLM(), events.append)
    assert plan_res["plan"]["intent"] == "general_inquiry"
    assert plan_res["plan"]["steps"] == ["advisor"]

    # 2. Advisor produces clear guidance with alternative suggestions
    state["plan"] = plan_res["plan"]
    advisor_res = run_advisor(state, MissingColumnLLM(), events.append)
    assert advisor_res["report"]["title"] == "Pemberitahuan Kolom Tidak Ditemukan"
    assert "gaji" in advisor_res["report"]["headline"]
    assert len(advisor_res["report"]["recommendations"]) > 0
