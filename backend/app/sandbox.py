"""Docker sandbox: runs ONE untrusted script in a throwaway container and streams what happens.

Containment applied to every run
- process isolation : separate container, never inside the app process
- no network        : network_mode="none"
- no secrets        : no environment variables except harmless ones; API keys live only in the orchestrator
- resource limits   : memory (no swap), CPU, pids, wall-clock timeout, output size, per-file size
- read-only rootfs  : only /output (bind, rw) and /tmp (tmpfs) are writable; /data and /code are read-only
- lifecycle         : container is force-removed after the run, success or not

`run()` is a generator: it yields event dicts for the live panel and *returns* a RunResult.
Use it as:   result = yield from sandbox.run(...)
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import ImageNotFound, NotFound

from .config import Settings
from .events import ev

log = logging.getLogger(__name__)

MAX_CAPTURE_CHARS = 200_000  # kept for feeding back to the LLM / evidence
MAX_EMIT_LINES = 400  # streamed to the browser per stream (stdout / stderr)
MAX_LINE_CHARS = 2_000


@dataclass
class RunResult:
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    outputs: list[str]
    output_dir: Path
    reason: str | None = None  # "timeout" | "oom" | "output_limit" | None
    duration_s: float = 0.0
    peak_mem_mb: float = 0.0


def safe_file(base: Path, name: str, max_bytes: int) -> Path | None:
    """Return base/name only if it is a plain file directly inside `base` (no symlinks, size-capped).

    The sandbox can write anything into its output dir, including symlinks pointing at host files,
    so the orchestrator must never read an output file without going through this check.
    """
    p = base / name
    try:
        if p.is_symlink() or not p.is_file():
            return None
        if p.resolve().parent != base.resolve():
            return None
        if p.stat().st_size > max_bytes:
            return None
    except OSError:
        return None
    return p


def _dir_size(path: Path, max_files: int = 2000) -> int:
    """Total bytes of regular files under `path` (symlinks not followed). Too many files => 'huge'."""
    total = 0
    count = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            count += 1
            if count > max_files:
                return 1 << 60
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _put(q: queue.Queue, item) -> None:
    try:
        q.put_nowait(item)
    except queue.Full:
        pass  # a script that floods output must not exhaust the orchestrator's memory


def parse_stats(st: dict) -> dict:
    mem = st.get("memory_stats", {}) or {}
    usage = mem.get("usage", 0) or 0
    cache = (mem.get("stats") or {}).get("inactive_file", (mem.get("stats") or {}).get("cache", 0)) or 0
    mem_mb = max(usage - cache, 0) / 1048576

    cpu = st.get("cpu_stats", {}) or {}
    pre = st.get("precpu_stats", {}) or {}
    cpu_delta = (cpu.get("cpu_usage", {}).get("total_usage", 0) or 0) - (pre.get("cpu_usage", {}).get("total_usage", 0) or 0)
    sys_delta = (cpu.get("system_cpu_usage", 0) or 0) - (pre.get("system_cpu_usage", 0) or 0)
    ncpu = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
    cpu_pct = (cpu_delta / sys_delta) * ncpu * 100 if sys_delta > 0 and cpu_delta >= 0 else 0.0
    return {"mem_mb": round(mem_mb, 1), "cpu_pct": round(cpu_pct, 1)}


class DockerSandbox:
    def __init__(self, settings: Settings):
        self.s = settings
        self._client: docker.DockerClient | None = None

    # ---------------------------------------------------------------- infra helpers
    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def health(self) -> dict:
        try:
            client = self._get_client()
            client.ping()
            try:
                client.images.get(self.s.sandbox_image)
                image = True
            except ImageNotFound:
                image = False
            return {"docker": True, "sandbox_image": image}
        except Exception:
            return {"docker": False, "sandbox_image": False}

    def cleanup_orphans(self) -> int:
        """Remove sandbox containers left behind by a crashed/restarted backend."""
        removed = 0
        try:
            for c in self._get_client().containers.list(all=True, filters={"label": "app=agent-analyst"}):
                try:
                    c.remove(force=True, v=True)
                    removed += 1
                except Exception:
                    pass
        except Exception:
            pass
        return removed

    @staticmethod
    def _destroy(container) -> bool:
        if container is None:
            return False
        try:
            container.remove(force=True, v=True)
            return True
        except NotFound:
            return True
        except Exception:
            log.exception("failed to remove sandbox container")
            return False

    # ---------------------------------------------------------------- stream pumps (threads)
    @staticmethod
    def _pump_logs(container, kind: str, q: queue.Queue, stop: threading.Event) -> None:
        buf = b""
        try:
            stream = container.logs(stream=True, follow=True, stdout=(kind == "stdout"), stderr=(kind == "stderr"))
            for chunk in stream:
                if stop.is_set():
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    _put(q, (kind, line.decode("utf-8", "replace").rstrip("\r")))
                if len(buf) > 65536:  # one giant line without newline
                    _put(q, (kind, buf.decode("utf-8", "replace")))
                    buf = b""
            if buf:
                _put(q, (kind, buf.decode("utf-8", "replace")))
        except Exception:
            pass

    def _pump_stats(self, container, q: queue.Queue, stop: threading.Event) -> None:
        try:
            for st in container.stats(stream=True, decode=True):
                if stop.is_set():
                    break
                stats_dict = parse_stats(st)
                stats_dict["mem_limit_mb"] = self.s.sandbox_memory_mb
                _put(q, ("stats", stats_dict))
        except Exception:
            pass

    # ---------------------------------------------------------------- the run
    def run(
        self, *, script: str, data_dir: Path, run_dir: Path, step: str, attempt: int
    ) -> Generator[dict, None, RunResult]:
        s = self.s
        code_dir, out_dir = run_dir / "code", run_dir / "output"
        for d in (code_dir, out_dir):
            d.mkdir(parents=True, exist_ok=True)
        (code_dir / "script.py").write_text(script, encoding="utf-8")
        os.chmod(code_dir, 0o755)
        os.chmod(code_dir / "script.py", 0o644)
        os.chmod(out_dir, 0o777)  # the sandbox user (uid 1000) must be able to write here

        limits = {
            "memory_mb": s.sandbox_memory_mb,
            "cpus": s.sandbox_cpus,
            "timeout_s": s.sandbox_timeout_s,
            "pids": s.sandbox_pids,
            "output_mb": s.sandbox_output_mb,
        }
        client = self._get_client()
        container = None
        cid = ""
        result: RunResult | None = None
        stop = threading.Event()
        t0 = time.monotonic()
        captured = {"stdout": [], "stderr": []}
        sizes = {"stdout": 0, "stderr": 0}
        emitted = {"stdout": 0, "stderr": 0}
        peak = {"mem": 0.0}
        reason: str | None = None

        try:
            fsize = s.sandbox_output_mb * 1024 * 1024
            container = client.containers.create(
                image=s.sandbox_image,
                command=["python", "-I", "/code/script.py"],
                working_dir="/output",
                network_mode="none",
                mem_limit=f"{s.sandbox_memory_mb}m",
                memswap_limit=f"{s.sandbox_memory_mb}m",  # == mem_limit -> no swap
                nano_cpus=int(s.sandbox_cpus * 1_000_000_000),
                pids_limit=s.sandbox_pids,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                user="1000:1000",
                environment={"MPLBACKEND": "Agg", "HOME": "/tmp", "MPLCONFIGDIR": "/tmp/mpl"},
                volumes={
                    str(data_dir): {"bind": "/data", "mode": "ro"},
                    str(code_dir): {"bind": "/code", "mode": "ro"},
                    str(out_dir): {"bind": "/output", "mode": "rw"},
                },
                ulimits=[docker.types.Ulimit(name="fsize", soft=fsize, hard=fsize)],
                log_config=docker.types.LogConfig(
                    type=docker.types.LogConfig.types.JSON, config={"max-size": "2m", "max-file": "1"}
                ),
                labels={"app": "agent-analyst"},
            )
            cid = container.short_id
            yield ev(
                "sandbox_created",
                step=step,
                attempt=attempt,
                container=cid,
                limits=limits,
                network="disabled",
                secrets="none",
                rootfs="read-only",
            )
            container.start()
            yield ev("sandbox_started", step=step, attempt=attempt, container=cid)

            q: queue.Queue = queue.Queue(maxsize=5000)
            log_threads = [
                threading.Thread(target=self._pump_logs, args=(container, k, q, stop), daemon=True)
                for k in ("stdout", "stderr")
            ]
            for t in log_threads:
                t.start()
            threading.Thread(target=self._pump_stats, args=(container, q, stop), daemon=True).start()

            def consume(items):
                for kind, payload in items:
                    if kind == "stats":
                        peak["mem"] = max(peak["mem"], payload["mem_mb"])
                        yield ev("stats", step=step, attempt=attempt, **payload)
                        continue
                    if sizes[kind] < MAX_CAPTURE_CHARS:
                        captured[kind].append(payload + "\n")
                        sizes[kind] += len(payload) + 1
                    if emitted[kind] < MAX_EMIT_LINES:
                        emitted[kind] += 1
                        yield ev(kind, step=step, attempt=attempt, text=payload[:MAX_LINE_CHARS])
                    elif emitted[kind] == MAX_EMIT_LINES:
                        emitted[kind] += 1
                        yield ev(kind, step=step, attempt=attempt, text="[... further output not streamed ...]")

            def drain_queue():
                items = []
                while True:
                    try:
                        items.append(q.get_nowait())
                    except queue.Empty:
                        return items

            deadline = t0 + s.sandbox_timeout_s
            output_cap = s.sandbox_output_mb * 1024 * 1024

            while True:
                items = []
                try:
                    items.append(q.get(timeout=0.25))
                except queue.Empty:
                    pass
                items += drain_queue()
                yield from consume(items)

                container.reload()
                if container.status in ("exited", "dead", "removing"):
                    break
                if time.monotonic() > deadline:
                    reason = "timeout"
                elif _dir_size(out_dir) > output_cap:
                    reason = "output_limit"
                if reason:
                    try:
                        container.kill()
                    except Exception:
                        pass
                    break

            for t in log_threads:  # let the log readers flush the tail of the output
                t.join(timeout=2)
            yield from consume(drain_queue())

            container.reload()
            state = container.attrs.get("State", {}) or {}
            exit_code = state.get("ExitCode")
            if state.get("OOMKilled") and reason is None:
                reason = "oom"

            if reason:
                messages = {
                    "timeout": f"Stopped: exceeded the {s.sandbox_timeout_s}s time limit",
                    "oom": f"Stopped: exceeded the {s.sandbox_memory_mb}MB memory limit (OOM-killed)",
                    "output_limit": f"Stopped: wrote more than {s.sandbox_output_mb}MB (or too many files)",
                }
                yield ev("limit_hit", step=step, attempt=attempt, kind=reason, message=messages[reason])

            duration = round(time.monotonic() - t0, 2)
            outputs = sorted(p.name for p in out_dir.iterdir() if p.is_file() and not p.is_symlink())[:100]
            result = RunResult(
                ok=(exit_code == 0 and reason is None),
                exit_code=exit_code,
                stdout="".join(captured["stdout"]),
                stderr="".join(captured["stderr"]),
                outputs=outputs,
                output_dir=out_dir,
                reason=reason,
                duration_s=duration,
                peak_mem_mb=round(peak["mem"], 1),
            )
            yield ev(
                "sandbox_finished",
                step=step,
                attempt=attempt,
                ok=result.ok,
                exit_code=exit_code,
                duration_s=duration,
                peak_mem_mb=result.peak_mem_mb,
                outputs=outputs,
            )
        except Exception as exc:
            log.exception("Sandbox execution failed in step %s attempt %d: %s", step, attempt, exc)
            duration = round(time.monotonic() - t0, 2)
            outputs = sorted(p.name for p in out_dir.iterdir() if p.is_file() and not p.is_symlink())[:100] if out_dir.is_dir() else []
            result = RunResult(
                ok=False,
                exit_code=1,
                stdout="".join(captured["stdout"]),
                stderr=f"Sandbox error: {exc}\n" + "".join(captured["stderr"]),
                outputs=outputs,
                output_dir=out_dir,
                reason=reason or "error",
                duration_s=duration,
                peak_mem_mb=round(peak["mem"], 1),
            )
            yield ev(
                "sandbox_finished",
                step=step,
                attempt=attempt,
                ok=False,
                exit_code=1,
                duration_s=duration,
                peak_mem_mb=result.peak_mem_mb,
                outputs=outputs,
            )
        finally:
            stop.set()
            destroyed = self._destroy(container)
            if cid or container:
                yield ev(
                    "sandbox_destroyed",
                    step=step,
                    attempt=attempt,
                    container=cid or "unknown",
                    ok=destroyed,
                    lifetime_s=round(time.monotonic() - t0, 2),
                )

        assert result is not None
        return result
