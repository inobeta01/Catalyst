"""Triage agent: classifies an incoming issue and routes it to a downstream worker.

Three LangGraph nodes, each powered by a concrete Gemini model:

    initial_classify -> fetch_context -> refined_classify

Step contracts:
- ``initial_classify`` (gemini-1.5-flash): cheap first-pass priority label.
- ``fetch_context``: MCP tool call; no LLM.
- ``refined_classify`` (gemini-1.5-pro): final priority + routing decision.
"""
import re
from typing import Annotated, List, Optional, TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from workload.llm import safe_llm_call
from workload.prompts.triage import TRIAGE_PROMPT
from workload.tools import fetch_issue_context


# Explicit route allowlist — keeps the LLM from inventing worker names.
_ALLOWED_ROUTES = {
    "code-writer",
    "code-review",
    "brief-writer",
    "triage",
}


class TriageState(TypedDict):
    messages: Annotated[List, add_messages]
    issue_id: Optional[str]
    issue_text: Optional[str]
    initial_classification: Optional[str]
    context: Optional[dict]
    refined_classification: Optional[str]
    priority: Optional[str]            # P0 | P1 | P2
    route_target: Optional[str]         # code-writer | code-review | brief-writer | triage
    trace_span_kind: Optional[str]


_INITIAL_PROMPT_TEMPLATE = (
    "Classify this issue by priority (P0, P1, or P2) and give a one-line reason.\n"
    "Respond with exactly two lines:\n"
    "Priority: <P0|P1|P2>\n"
    "Reason: <one sentence>\n\n"
    "Issue:\n{issue}\n"
)


_REFINED_PROMPT_TEMPLATE = (
    "Re-classify the issue below using the full context. Output exactly four lines:\n"
    "Priority: <P0|P1|P2>\n"
    "Reason: <one sentence citing the context>\n"
    "Route: <one of: code-writer, code-review, brief-writer, triage>\n"
    "Confidence: <low|medium|high>\n\n"
    "Issue:\n{issue}\n\n"
    "Full context:\n{context}\n"
)


_PRIORITY_RE = re.compile(r"\b(P[012])\b", re.IGNORECASE)
_ROUTE_RE = re.compile(r"\b(" + "|".join(sorted(_ALLOWED_ROUTES)) + r")\b", re.IGNORECASE)


def _extract_priority(text: str) -> str:
    match = _PRIORITY_RE.search(text)
    return match.group(1).upper() if match else "P2"


def _extract_route(text: str) -> str:
    match = _ROUTE_RE.search(text)
    return match.group(1).lower() if match else "triage"


def initial_classify(state: TriageState) -> TriageState:
    """Step 1 — cheap flash model gives a first-pass priority."""
    issue = state.get("issue_text", "")
    prompt = _INITIAL_PROMPT_TEMPLATE.format(issue=issue)
    classification = safe_llm_call(
        prompt,
        system_prompt=TRIAGE_PROMPT,
        model_name="gemini-fast",
        temperature=0.2,
        max_output_tokens=128,
    )
    return {
        **state,
        "initial_classification": classification,
        "priority": _extract_priority(classification),
        "trace_span_kind": "triage.initial_classify",
    }


def fetch_context(state: TriageState) -> TriageState:
    """Step 2 — pull issue context via the MCP-backed tool."""
    issue_id = state.get("issue_id") or "unknown"
    context = fetch_issue_context(issue_id)
    return {
        **state,
        "context": context,
        "trace_span_kind": "triage.fetch_context",
    }


def refined_classify(state: TriageState) -> TriageState:
    """Step 3 — gemini-pro re-evaluates with context and chooses a route."""
    issue = state.get("issue_text", "")
    context = state.get("context", {})
    prompt = _REFINED_PROMPT_TEMPLATE.format(issue=issue, context=context)

    refined = safe_llm_call(
        prompt,
        system_prompt=TRIAGE_PROMPT,
        model_name="gemini-pro",
        temperature=0.2,
        max_output_tokens=256,
    )
    priority = _extract_priority(refined)
    route = _extract_route(refined)

    return {
        **state,
        "refined_classification": refined,
        "priority": priority,
        "route_target": route,
        "trace_span_kind": "triage.refined_classify",
    }


def build_triage_agent():
    graph = StateGraph(TriageState)
    graph.add_node("initial", initial_classify)
    graph.add_node("fetch", fetch_context)
    graph.add_node("refine", refined_classify)
    graph.set_entry_point("initial")
    graph.add_edge("initial", "fetch")
    graph.add_edge("fetch", "refine")
    graph.set_finish_point("refine")
    return graph.compile()


def create_agent():
    return build_triage_agent()


# Exported compiled agent for the orchestration layer.
agent = create_agent()
