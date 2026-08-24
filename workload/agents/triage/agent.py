"""Triage agent: classifies issues and routes them with multi-step LLM reasoning, tool calls, and FreeLLM API.
"""
from langgraph.graph import StateGraph
from typing import TypedDict, Optional, List, Annotated
from langgraph.graph.message import add_messages
from workload.prompts.triage import TRIAGE_PROMPT
from workload.llm import safe_llm_call
from workload.tools import fetch_issue_context

class TriageState(TypedDict):
    messages: Annotated[List, add_messages]
    issue_id: Optional[str]
    issue_text: Optional[str]
    initial_classification: Optional[str]
    refined_classification: Optional[str]
    route_target: Optional[str]
    trace_span_kind: Optional[str]

def initial_classify(state: TriageState) -> TriageState:
    """Step 1 – quick classification using a lightweight LLM (auto:fast)."""
    issue = state.get("issue_text", "")
    prompt = f"Classify the following issue with priority (P0/P1/P2) and give a short route hint: {issue}"
    classification = safe_llm_call(prompt, system_prompt=TRIAGE_PROMPT, model_name="auto:fast")
    return {**state, "initial_classification": classification.strip(), "trace_span_kind": "triage.initial_classify"}

def fetch_context(state: TriageState) -> TriageState:
    """Step 2 – fetch full context for the issue via a tool call."""
    issue_id = state.get("issue_id") or "unknown"
    context = fetch_issue_context(issue_id)
    # Attach context as part of the state for further LLM refinement.
    return {**state, "context": context, "trace_span_kind": "triage.fetch_context"}

def refined_classify(state: TriageState) -> TriageState:
    """Step 3 – refine classification using richer context and a stronger LLM.
    Uses a different model (e.g., Claude 3.5 Sonnet) via the FreeLLM auto‑routing.
    """
    issue = state.get("issue_text", "")
    context = state.get("context", {})
    # Assemble a richer prompt.
    prompt = (
        f"Issue: {issue}\n\n"
        f"Full context: {context}\n\n"
        "Given the full context, re‑classify the issue with priority (P0/P1/P2) and a definitive routing target (code‑review, brief‑writer, etc.)."
    )
    refined = safe_llm_call(prompt, system_prompt=TRIAGE_PROMPT, model_name="gpt-4o-mini")
    # Simple heuristic to parse route from LLM response.
    route = "code-review" if "bug" in refined.lower() else "brief-writer"
    return {
        **state,
        "refined_classification": refined.strip(),
        "route_target": route,
        "trace_span_kind": "triage.refined_classify",
    }

def build_triage_agent():
    graph = StateGraph(TriageState)
    graph.add_node("initial", initial_classify)
    graph.add_node("fetch", fetch_context)
    graph.add_node("refine", refined_classify)
    # Linear workflow: initial -> fetch -> refine
    graph.set_entry_point("initial")
    graph.add_edge("initial", "fetch")
    graph.add_edge("fetch", "refine")
    graph.set_finish_point("refine")
    return graph.compile()

agent = build_triage_agent()
