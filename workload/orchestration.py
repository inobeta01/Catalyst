"""Orchestration: Unified LangGraph agency workflow combining Triage, Code Writer, Code Review, and Brief Writer agents connected via the shared MCP cache.
"""

from typing import TypedDict, Optional, List, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Import agent modules
from workload.agents.triage.agent import agent as triage_agent
from workload.agents.code_writer.agent import agent as code_writer_agent
from workload.agents.code_review.agent import agent as code_review_agent
from workload.agents.brief_writer.agent import agent as brief_writer_agent
from workload.tools.mcp import MCP


class AgencyState(TypedDict):
    messages: Annotated[List, add_messages]
    task_id: str
    issue_text: str
    route_target: Optional[str]  # e.g., "code-writer", "brief-writer", etc.
    final_output: Optional[dict]
    trace_span_kind: Optional[str]


def run_triage(state: AgencyState) -> AgencyState:
    """Execute the Triage agent sub-graph and store its outcome in the shared MCP cache."""
    task_id = state.get("task_id", "default-run")
    issue_text = state.get("issue_text", "")

    # Invoke the triage sub-graph
    sub_output = triage_agent.invoke({
        "issue_id": task_id,
        "issue_text": issue_text,
        "messages": state.get("messages", [])
    })

    route = sub_output.get("route_target", "code-writer")

    # Store result in shared MCP cache so downstream agents can access it seamlessly
    with MCP(task_id=task_id) as cache:
        cache.set("triage_result", {
            "initial_classification": sub_output.get("initial_classification"),
            "refined_classification": sub_output.get("refined_classification"),
            "description": issue_text,
            "route_target": route
        })

    return {
        **state,
        "route_target": route,
        "trace_span_kind": "orchestration.triage_completed"
    }


def run_code_writer(state: AgencyState) -> AgencyState:
    """Execute the Code Writer agent sub-graph, reading task details from MCP and persisting its result to the shared cache."""
    task_id = state.get("task_id", "default-run")

    # Run code writer agent
    sub_output = code_writer_agent.invoke({
        "issue_id": task_id,
        "messages": state.get("messages", [])
    })

    # Persist result to MCP for downstream agents (e.g., brief writer)
    from workload.tools.mcp import MCP
    with MCP(task_id=task_id) as cache:
        cache.set("code_writer_result", sub_output.get("generated_code"))

    return {
        **state,
        "final_output": sub_output.get("generated_code"),
        "trace_span_kind": "orchestration.code_writer_completed"
    }


def run_code_review(state: AgencyState) -> AgencyState:
    """Execute the Code Review agent sub-graph."""
    task_id = state.get("task_id", "default-run")

    sub_output = code_review_agent.invoke({
        "pr_id": task_id,
        "messages": state.get("messages", [])
    })

    return {
        **state,
        "final_output": {"verdict": sub_output.get("final_verdict")},
        "trace_span_kind": "orchestration.code_review_completed"
    }


def run_brief_writer(state: AgencyState) -> AgencyState:
    """Execute the Brief Writer agent sub-graph."""
    task_id = state.get("task_id", "default-run")

    # Brief writer agent can also read context from MCP cache if needed
    with MCP(task_id=task_id) as cache:
        triage_data = cache.get("triage_result", {})

    # Simple stub execution for brief writer
    return {
        **state,
        "final_output": {"brief": f"Technical brief generated for: {triage_data.get('description', '')}"},
        "trace_span_kind": "orchestration.brief_writer_completed"
    }


def route_decision(state: AgencyState) -> str:
    """Conditional router based on route_target stored in state / MCP."""
    route = state.get("route_target", "")
    if "code" in route or "bug" in route:
        return "code_writer"
    elif "review" in route:
        return "code_review"
    else:
        return "brief_writer"


def build_agency_orchestrator():
    """Build the master LangGraph orchestrating all agents via shared MCP."""
    graph = StateGraph(AgencyState)

    graph.add_node("triage", run_triage)
    graph.add_node("code_writer", run_code_writer)
    graph.add_node("code_review", run_code_review)
    graph.add_node("brief_writer", run_brief_writer)

    graph.set_entry_point("triage")

    # Conditional routing from Triage to specialized worker agent
    graph.add_conditional_edges(
        "triage",
        route_decision,
        {
            "code_writer": "code_writer",
            "code_review": "code_review",
            "brief_writer": "brief_writer"
        }
    )

    graph.add_edge("code_writer", END)
    graph.add_edge("code_review", END)
    graph.add_edge("brief_writer", END)

    return graph.compile()


# Master orchestrator instance
agency_orchestrator = build_agency_orchestrator()

if __name__ == "__main__":
    import uuid
    run_id = uuid.uuid4().hex[:8]
    print(f"Starting test agency orchestrator run: {run_id}")
    initial_state = {
        "task_id": run_id,
        "issue_text": "Fix a null pointer bug in authentication module and write proper checks",
        "messages": []
    }
    result = agency_orchestrator.invoke(initial_state)
    print("Orchestration finished. Result:", result)
