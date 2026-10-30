"""Multi-Agent orchestrator using LangGraph.

Decomposed Specialist Agents:
- Profiler (agents/profiler.py): Executes sandboxed profiling script to extract schema and stats.
- Planner (agents/planner.py): Formulates analytical steps and checklist via LLM.
- Cleaner (agents/cleaner.py): Self-healing data sanitization loop and diff tracking.
- EDA (agents/eda.py): Exploratory data analysis, chart generation, and data quality checks.
- Reporter (agents/reporter.py): Executive synthesis with verified citation grounding.

Orchestrated via StateGraph in graph.py, exposing backward-compatible Agent.run() generator.
"""
from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Generator

from .agents import AgentState
from .config import Settings
from .events import ev
from .graph import create_agent_graph
from .jobs import Job
from .llm import LLM

log = logging.getLogger(__name__)

# ==============================================================================
# COMPLETION MARKER & ERROR WRAPPER (THREAD-SAFE COMMUNICATION)
# ==============================================================================

# Unique sentinel object marker.
# Placed onto the inter-thread queue to signal that the entire LangGraph workflow has finished.
_SENTINEL = object()


class _ErrorWrapper:
    """Wrapper to safely transmit unexpected exceptions from worker thread to caller."""

    def __init__(self, exc: BaseException):
        self.exc = exc


# ==============================================================================
# AGENT FACADE CLASS
# ==============================================================================

class Agent:
    """Multi-Agent Orchestrator Facade using LangGraph.

    Acts as a facade bridging the caller system (jobs.py) with the 5-agent LangGraph workflow.
    Provides a generator-based run() method so progress events stream in real time to SSE clients.
    """

    def __init__(self, llm: LLM, sandbox, settings: Settings):
        """Initialize dependencies and compile the LangGraph StateGraph once upfront."""
        self.llm = llm            # LLM inference engine (OpenAI / Vultr)
        self.sandbox = sandbox    # Code execution sandbox (Docker / LocalSandbox)
        self.s = settings         # System configuration (timeouts, retries, work dirs)
        self.graph = create_agent_graph()  # Assembles and compiles the 5-agent StateGraph

    def run(self, job: Job) -> Generator[dict, None, None]:
        """Execute the multi-agent pipeline and stream event dictionaries in real time.

        Notes on Generator[dict, None, None]:
        - 'Generator' represents the stream channel/pipe (not the data payload itself).
        - 'dict' is the data payload yielded on each event emission.
        - Each 'yield event' pauses this function momentarily, allowing jobs.py to execute
          job.add(event) and broadcast it immediately to the browser via SSE.
        """
        s = self.s

        # 1. Initial event: Notify frontend that analysis has started
        yield ev("job_started", job_id=job.id, query=job.query, filename=job.filename, max_attempts=s.max_retries)

        # 2. Thread-safe message queue for the Producer-Consumer communication pattern
        q: queue.Queue = queue.Queue()

        # 3. First-class function callback / emitter.
        #    Passed as a reference (without parentheses) so specialist agents can emit
        #    real-time event dictionaries into queue `q` during execution.
        def emit(event: dict) -> None:
            q.put(event)

        # 4. Initial Shared Workflow State (State / Mutable Payload)
        #    This shared state dictionary is passed and populated by each specialist node.
        initial_state: AgentState = {
            "job": job,
            "profile": None,
            "plan": None,
            "clean_result": None,
            "eda_result": None,
            "report": None,
            "evidence": job.evidence,
            "warnings": job.warnings,
            "needs_reclean": False,
            "reclean_count": 0,
            "error": None,
        }

        # 5. Background worker function executing LangGraph in a dedicated thread.
        #    Why run in a separate thread?
        #    graph.invoke() is blocking (waits until all nodes finish before returning).
        #    Running it in a dedicated thread allows LangGraph to execute in the background
        #    while emitting events into `q` without freezing the SSE stream generator.
        def _runner():
            try:
                # Trigger LangGraph execution:
                # - Argument 1: initial_state (Mutable State / Payload)
                # - Argument 2: config["configurable"] (Immutable Tooling / Dependency Injection)
                self.graph.invoke(
                    initial_state,
                    config={
                        "configurable": {
                            "llm": self.llm,          # Reasoning and code generation tool
                            "sandbox": self.sandbox,  # Isolated Docker sandbox tool
                            "settings": self.s,       # Configuration parameters
                            "emitter": emit,          # Real-time event emitter callback
                        }
                    },
                )
            except BaseException as exc:
                log.exception("Agent graph execution failed")
                q.put(_ErrorWrapper(exc))
            finally:
                # Place sentinel marker when graph finishes (whether successful or failed)
                q.put(_SENTINEL)

        # 6. Start the LangGraph execution worker thread
        worker = threading.Thread(target=_runner, daemon=True)
        worker.start()

        # 7. Main Thread: Act as Consumer reading events from `q` and yielding them out
        has_failed = False
        while True:
            item = q.get()  # Block until next event is available in queue

            # If sentinel marker is reached, background graph execution has finished
            if item is _SENTINEL:
                break

            # Re-raise any unexpected exception caught in worker thread
            if isinstance(item, _ErrorWrapper):
                raise item.exc

            # If item is a valid event dictionary:
            if isinstance(item, dict):
                if item.get("type") == "job_failed":
                    has_failed = True
                # STREAM EVENT TO JOBS.PY:
                # Function pauses here, jobs.py executes job.add(item) -> streams via SSE,
                # then execution resumes to fetch the next queued item.
                yield item

        # 8. Ensure worker thread has completely terminated
        worker.join()

        # 9. Final event: Emit job_done if workflow completed successfully
        if not has_failed:
            yield ev("job_done", job_id=job.id, warnings=job.warnings)
