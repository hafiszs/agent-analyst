"""Tests that need neither Docker nor a real LLM.

LocalSandbox is a TEST DOUBLE that runs scripts with the local interpreter (NOT isolated).
It only exists to exercise the agent loop and the API end to end. The real isolation lives in app/sandbox.py.
"""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent import Agent
from app.config import get_settings
from app.events import ev
from app.jobs import Job
from app.main import create_app
from app.sandbox import RunResult, parse_stats, safe_file

DEMO_CSV = Path(__file__).resolve().parents[2] / "demo-data" / "messy_transactions.csv"

CLEAN_BROKEN = "import pandas as pd\ndf = pd.read_csv('/data/raw.csv')\nprint(df['kolom_tidak_ada'])\n"

CLEAN_FIXED = '''
import json
import pandas as pd

df = pd.read_csv('/data/raw.csv')
before = len(df)
df['vendor'] = df['vendor'].str.strip().str.title()
df['kategori'] = df['kategori'].str.strip().str.title()
df['status'] = df['status'].str.strip().str.lower()
df['jumlah'] = pd.to_numeric(df['jumlah'].astype(str).str.replace(r'[^0-9]', '', regex=True), errors='coerce')
df['tanggal'] = pd.to_datetime(df['tanggal'], format='mixed', dayfirst=True, errors='coerce')
dups = int(df.duplicated().sum())
df = df.drop_duplicates()
df.to_csv('/output/clean.csv', index=False)
changes = [
    {"column": "jumlah", "action": "parse rupiah text to number", "rows_affected": int(df['jumlah'].notna().sum()),
     "detail": "removed Rp and thousand separators", "examples": [{"before": "Rp 1.500.000", "after": "1500000"}]},
    {"column": None, "action": "drop duplicate rows", "rows_affected": dups, "detail": "exact duplicates", "examples": []},
]
json.dump({"rows_before": before, "rows_after": len(df), "changes": changes}, open('/output/changes.json', 'w'))
print('rows', before, '->', len(df))
'''

EDA = '''
import json
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/data/clean.csv')
per_vendor = df.groupby('vendor')['jumlah'].sum().sort_values(ascending=False)
top = str(per_vendor.index[0])
share = round(float(per_vendor.iloc[0] / per_vendor.sum() * 100), 1)
per_vendor.plot(kind='bar')
plt.savefig('/output/chart_1.png', dpi=80, bbox_inches='tight')
plt.close()
results = [{"id": "f1", "title": "Spending per vendor", "statement": f"{top} accounts for {share}% of total spending.",
            "evidence": {"top_vendor": top, "share_pct": share}, "chart": "chart_1.png"}]
json.dump(results, open('/output/results.json', 'w'))
print(per_vendor)
'''


def fenced(code: str) -> str:
    return "```python\n" + code.strip() + "\n```"


class FakeLLM:
    configured = True

    def __init__(self):
        self.clean_calls = 0

    def chat(self, messages, json_mode=False):
        system = messages[0]["content"]
        user = messages[1]["content"]
        if "planner of an AI data-analyst agent" in system:
            return json.dumps(
                {"intent": "full_analysis", "steps": ["clean", "eda", "report"], "plan": ["Clean", "Analyse", "Report"], "reason": "test"}
            )
        if "writing a report" in system or "Elite Lead Data Analyst" in system:
            return json.dumps(
                {
                    "title": "Test report",
                    "headline": "One vendor dominates spending.",
                    "verified_claims": [
                        {"text": "A vendor has a large share.", "evidence_ids": ["f1"]},
                        {"text": "Made-up claim.", "evidence_ids": ["does-not-exist"]},
                    ],
                    "interpretation": ["Possible concentration risk."],
                    "recommendations": ["Review the contract."],
                }
            )
        if "TASK: clean the dataset" in user:
            self.clean_calls += 1
            return fenced(CLEAN_BROKEN if self.clean_calls == 1 else CLEAN_FIXED)
        return fenced(EDA)


class LocalSandbox:
    def __init__(self, settings):
        self.s = settings

    def run(self, *, script, data_dir, run_dir, step, attempt):
        code_dir, out_dir = run_dir / "code", run_dir / "output"
        code_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        script = script.replace("/data", Path(data_dir).as_posix()).replace("/output", Path(out_dir).as_posix())
        path = (code_dir / "script.py").resolve()
        path.write_text(script, encoding="utf-8")
        yield ev("sandbox_created", step=step, attempt=attempt, container="local")
        env = {**os.environ, "MPLBACKEND": "Agg", "MPLCONFIGDIR": str(out_dir / ".mpl")}
        proc = subprocess.run(
            [sys.executable, str(path)], capture_output=True, text=True, timeout=120, cwd=out_dir,
            env=env,
        )
        for line in proc.stdout.splitlines():
            yield ev("stdout", step=step, attempt=attempt, text=line)
        yield ev("sandbox_destroyed", step=step, attempt=attempt, container="local")
        return RunResult(
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            outputs=sorted(p.name for p in out_dir.iterdir() if p.is_file()),
            output_dir=out_dir,
        )


def make_settings(tmp_path):
    return dataclasses.replace(get_settings(), work_dir=str(tmp_path), max_retries=3, job_ttl_s=3600)


def test_agent_flow_self_heals_and_validates_claims(tmp_path):
    settings = make_settings(tmp_path)
    job = Job("t1", tmp_path / "jobs", "Analisis pengeluaran per vendor", "demo.csv", "raw.csv")
    job.data_dir.mkdir(parents=True)
    job.artifacts_dir.mkdir(parents=True)
    (job.data_dir / "raw.csv").write_bytes(DEMO_CSV.read_bytes())

    llm = FakeLLM()
    events = list(Agent(llm, LocalSandbox(settings), settings).run(job))
    types = [e["type"] for e in events]

    assert types[0] == "job_started" and types[-1] == "job_done"
    assert "profile_ready" in types and "plan_ready" in types and "diff_ready" in types
    failed = [e for e in events if e["type"] == "attempt_failed" and e["step"] == "clean"]
    assert len(failed) == 1 and failed[0]["will_retry"] is True  # attempt 1 broke, error went back to the LLM
    assert [e["attempt"] for e in events if e["type"] == "attempt_succeeded" and e["step"] == "clean"] == [2]
    assert llm.clean_calls == 2

    claims = job.report["verified_claims"]
    assert [c["verified"] for c in claims] == [True, False]  # the claim without real evidence is flagged
    assert {"p0", "c1", "f1"} <= set(job.evidence)
    assert "clean.csv" in job.artifacts and "chart_1.png" in job.artifacts
    assert job.evidence["f1"]["code"].strip().startswith("import json")


def test_api_end_to_end(tmp_path):
    settings = make_settings(tmp_path)
    client = TestClient(create_app(settings, llm=FakeLLM(), sandbox=LocalSandbox(settings)))

    r = client.post(
        "/api/jobs",
        files={"file": ("demo.csv", DEMO_CSV.read_bytes(), "text/csv")},
        data={"query": "Analisis pengeluaran per vendor"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    for _ in range(300):
        info = client.get(f"/api/jobs/{job_id}").json()
        if info["status"] in ("done", "failed"):
            break
        time.sleep(0.2)
    assert info["status"] == "done", info

    sse = client.get(f"/api/jobs/{job_id}/events").text
    assert "event: sandbox_created" in sse and "event: job_done" in sse

    assert client.get(f"/api/jobs/{job_id}/evidence/f1").json()["code"]
    png = client.get(f"/api/jobs/{job_id}/files/chart_1.png")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    assert client.get(f"/api/jobs/{job_id}/files/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404

    bad = client.post("/api/jobs", files={"file": ("x.exe", b"abc", "application/octet-stream")}, data={"query": "hi"})
    assert bad.status_code == 415


def test_safe_file_rejects_symlinks_and_oversize(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("shh")
    (out / "ok.csv").write_text("col\nval\n")
    (out / "big.csv").write_text("x" * 200)
    try:
        (out / "link.png").symlink_to(secret)
        assert safe_file(out, "link.png", 1000) is None  # symlink to a host file
    except OSError:
        pass  # Windows unprivileged users cannot create symlinks without Developer Mode
    assert safe_file(out, "ok.csv", 1000) is not None
    assert safe_file(out, "big.csv", 10) is None  # too large
    assert safe_file(out, "../secret.txt", 1000) is None  # outside the directory


def test_parse_stats():
    st = {
        "memory_stats": {"usage": 200 * 1048576, "stats": {"inactive_file": 50 * 1048576}},
        "cpu_stats": {"cpu_usage": {"total_usage": 2_000_000}, "system_cpu_usage": 10_000_000, "online_cpus": 2},
        "precpu_stats": {"cpu_usage": {"total_usage": 1_000_000}, "system_cpu_usage": 6_000_000},
    }
    assert parse_stats(st) == {"mem_mb": 150.0, "cpu_pct": 50.0}
