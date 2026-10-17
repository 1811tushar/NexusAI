"""LangGraph graph (AI-AG-01, architecture doc section 3):
input_guard -> recall_memory -> supervisor -> planner -> (researcher | data_analyst) -> analyst -> verifier -> confidence_check
  -> (loop back to planner with a focus | action_planning) -> (approval_gate only if HIGH-risk proposals) -> reporter -> save_memory.
Loops are bounded by maxLoops (<= 5). The compiled graph uses the Postgres checkpointer keyed by thread_id; approval_gate calls interrupt().
Control flow is plain Python edges so the paths can be tested with a scripted LLM."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.action_planning import action_planning
from app.agents.nodes.analyst import analyst
from app.agents.nodes.approval_gate import approval_gate
from app.agents.nodes.confidence_check import confidence_check
from app.agents.nodes.data_analyst import data_analyst
from app.agents.nodes.input_guard import input_guard
from app.agents.nodes.planner import planner
from app.agents.nodes.recall_memory import recall_memory_node
from app.agents.nodes.reporter import reporter
from app.agents.nodes.researcher import researcher
from app.agents.nodes.save_memory import save_memory
from app.agents.nodes.supervisor import supervisor
from app.agents.nodes.verifier import verifier
from app.agents.state import AgentState


def _pending(state: dict[str, Any], agent: str) -> bool:
    return any(s["agent"] == agent and s["status"] == "PENDING" for s in state.get("plan", []))


def after_guard(state: dict[str, Any]) -> str:
    return END if state.get("refused") else "recall_memory"


def after_supervisor(state: dict[str, Any]) -> str:
    return "reporter" if state.get("trivial") else "planner"


def after_planner(state: dict[str, Any]) -> str:
    return "researcher" if _pending(state, "RESEARCHER") else ("data_analyst" if _pending(state, "DATA_ANALYST") else "analyst")


def after_researcher(state: dict[str, Any]) -> str:
    return "data_analyst" if _pending(state, "DATA_ANALYST") else "analyst"


def after_confidence(state: dict[str, Any]) -> str:
    return "planner" if state.get("decision") == "LOOP" else "action_planning"


def after_actions(state: dict[str, Any]) -> str:
    return "approval_gate" if state.get("pending_high") else "reporter"


def build_graph(checkpointer: Any) -> Any:
    g = StateGraph(AgentState)
    for name, fn in [("input_guard", input_guard), ("recall_memory", recall_memory_node), ("supervisor", supervisor), ("planner", planner),
                     ("researcher", researcher), ("data_analyst", data_analyst), ("analyst", analyst), ("verifier", verifier),
                     ("confidence_check", confidence_check), ("action_planning", action_planning), ("approval_gate", approval_gate),
                     ("reporter", reporter), ("save_memory", save_memory)]:
        g.add_node(name, fn)
    g.add_edge(START, "input_guard")
    g.add_conditional_edges("input_guard", after_guard, {END: END, "recall_memory": "recall_memory"})
    g.add_edge("recall_memory", "supervisor")
    g.add_conditional_edges("supervisor", after_supervisor, {"reporter": "reporter", "planner": "planner"})
    g.add_conditional_edges("planner", after_planner, {"researcher": "researcher", "data_analyst": "data_analyst", "analyst": "analyst"})
    g.add_conditional_edges("researcher", after_researcher, {"data_analyst": "data_analyst", "analyst": "analyst"})
    g.add_edge("data_analyst", "analyst")
    g.add_edge("analyst", "verifier")
    g.add_edge("verifier", "confidence_check")
    g.add_conditional_edges("confidence_check", after_confidence, {"planner": "planner", "action_planning": "action_planning"})
    g.add_conditional_edges("action_planning", after_actions, {"approval_gate": "approval_gate", "reporter": "reporter"})
    g.add_edge("approval_gate", "reporter")
    g.add_edge("reporter", "save_memory")
    g.add_edge("save_memory", END)
    return g.compile(checkpointer=checkpointer)
