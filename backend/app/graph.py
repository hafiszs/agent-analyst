from __future__ import annotations

import logging
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from .agents import (
    AgentState,
    run_advisor,
    run_cleaner,
    run_eda,
    run_planner,
    run_profiler,
    run_reporter,
)

log = logging.getLogger(__name__)


def node_profiler(state: AgentState, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    sandbox = configurable["sandbox"]
    emitter = configurable["emitter"]
    return run_profiler(state, sandbox, emitter)


def node_planner(state: AgentState, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    llm = configurable["llm"]
    emitter = configurable["emitter"]
    return run_planner(state, llm, emitter)


def node_advisor(state: AgentState, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    llm = configurable["llm"]
    emitter = configurable["emitter"]
    return run_advisor(state, llm, emitter)


def node_cleaner(state: AgentState, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    llm = configurable["llm"]
    sandbox = configurable["sandbox"]
    settings = configurable["settings"]
    emitter = configurable["emitter"]
    res = run_cleaner(state, llm, sandbox, settings, emitter)
    if state.get("reclean_count", 0) > 0 or state.get("needs_reclean"):
        res["reclean_count"] = state.get("reclean_count", 0) + 1
    return res


def node_eda(state: AgentState, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    llm = configurable["llm"]
    sandbox = configurable["sandbox"]
    settings = configurable["settings"]
    emitter = configurable["emitter"]
    return run_eda(state, llm, sandbox, settings, emitter)


def node_reporter(state: AgentState, config: RunnableConfig) -> dict:
    configurable = config.get("configurable", {})
    llm = configurable["llm"]
    emitter = configurable["emitter"]
    return run_reporter(state, llm, emitter)


def route_after_profiler(state: AgentState) -> str:
    if state.get("error") or not state.get("profile"):
        return "end"
    return "planner"


def route_after_planner(state: AgentState) -> str:
    plan = state.get("plan") or {}
    steps = plan.get("steps") or []
    intent = plan.get("intent")
    if intent == "general_inquiry" or "advisor" in steps:
        return "advisor"
    if "clean" in steps:
        return "cleaner"
    if "eda" in steps:
        return "eda"
    return "reporter"


def route_after_cleaner(state: AgentState) -> str:
    plan = state.get("plan") or {}
    steps = plan.get("steps") or []
    if "eda" in steps:
        return "eda"
    return "reporter"


def route_after_eda(state: AgentState) -> str:
    if state.get("needs_reclean") and state.get("reclean_count", 0) < 1:
        return "cleaner"
    return "reporter"


def create_agent_graph():
    """Build and compile the LangGraph StateGraph for multi-agent analytical workflow."""
    builder = StateGraph(AgentState)
    builder.add_node("profiler", node_profiler)
    builder.add_node("planner", node_planner)
    builder.add_node("advisor", node_advisor)
    builder.add_node("cleaner", node_cleaner)
    builder.add_node("eda", node_eda)
    builder.add_node("reporter", node_reporter)

    builder.add_edge(START, "profiler")
    builder.add_conditional_edges("profiler", route_after_profiler, {"planner": "planner", "end": END})
    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {"cleaner": "cleaner", "eda": "eda", "reporter": "reporter", "advisor": "advisor"},
    )
    builder.add_conditional_edges("cleaner", route_after_cleaner, {"eda": "eda", "reporter": "reporter"})
    builder.add_conditional_edges("eda", route_after_eda, {"cleaner": "cleaner", "reporter": "reporter"})
    builder.add_edge("reporter", END)
    builder.add_edge("advisor", END)

    return builder.compile()
