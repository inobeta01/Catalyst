"""Orchestration: Unified LangGraph agency workflow combining Triage, Code Writer, Code Review, and Brief Writer agents connected via the shared MCP cache.
"""

import os
from typing import TypedDict, Optional, List, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Import agent modules
from workload.agents.triage.agent import agent as triage_agent
from workload.agents.code_writer.agent import agent as code_writer_agent
from workload.agents.code_review.agent import agent as code_review_agent
from workload.agents.brief_writer.agent import agent as brief_writer_agent
from workload.tools.mcp import MCP
from workload.prompts.templates import get_task_by_id, get_failure_config


class AgencyState(TypedDict):
    messages: Annotated[List, add_messages]
    task_id: str
    issue_text: str
    route_target: Optional[str]  # e.g., "code-writer", "brief-writer", etc.
    final_output: Optional[dict]
    trace_span_kind: Optional[str]


def _check_failure(failure_mode: str) -> None:
    """Raise an exception if the corresponding failure env var is set."""
    env_map = {
        "agent_crash": "AGENT_FAIL",
        "plugin_build_error": "PLUGIN_BUILD_ERR",
        "workflow_exception": "LANGGRAPH_ERR",
        "network_timeout": "HTTP_TIMEOUT",
        "partial_success": "PARTIAL_SUCCESS",
    }
    env_var = env_map.get(failure_mode)
    if env_var and os.getenv(env_var) == "1":
        raise RuntimeError(f"Simulated {failure_mode} failure triggered by {env_var}=1")


def run_triage(state: AgencyState) -> AgencyState:
    """Execute the Triage agent sub-graph and store its outcome in the shared MCP cache."""
    task_id = state.get("task_id", "default-run")
    issue_text = state.get("issue_text", "")

    # Simulate failure if configured for this task
    failure_cfg = get_failure_config(task_id)
    if failure_cfg:
        _check_failure(failure_cfg.get("failure_mode"))

    # Invoke the triage sub-graph
    sub_output = triage_agent.invoke({
        "issue_id": task_id,
        "issue_text": issue_text,
        "messages": state.get("messages", [])
    })

    route = sub_output.get("route_target", "code-writer")

    # Store result in shared MCP cache so downstream agents can access it seamlessly
    with MCP(task_id=task_id) as cache:
        cache.set("triage_output", {
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

    # Simulate failure if configured for this task
    failure_cfg = get_failure_config(task_id)
    if failure_cfg:
        _check_failure(failure_cfg.get("failure_mode"))

    # Run code writer agent
    sub_output = code_writer_agent.invoke({
        "issue_id": task_id,
        "messages": state.get("messages", [])
    })

    # Persist result to MCP for downstream agents (e.g., brief writer)
    from workload.tools.mcp import MCP
    with MCP(task_id=task_id) as cache:
        cache.set("code_output", sub_output.get("generated_code"))

    return {
        **state,
        "final_output": sub_output.get("generated_code"),
        "trace_span_kind": "orchestration.code_writer_completed"
    }


def run_code_review(state: AgencyState) -> AgencyState:
    """Execute the Code Review agent sub-graph."""
    task_id = state.get("task_id", "default-run")

    # Simulate failure if configured for this task
    failure_cfg = get_failure_config(task_id)
    if failure_cfg:
        _check_failure(failure_cfg.get("failure_mode"))

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

    # Simulate failure if configured for this task
    failure_cfg = get_failure_config(task_id)
    if failure_cfg:
        _check_failure(failure_cfg.get("failure_mode"))

    # Brief writer agent can also read context from MCP cache if needed
    with MCP(task_id=task_id) as cache:
        triage_data = cache.get("triage_output", {})

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


def parse_status_file(status_path: str = "STATUS.md"):
    """Parse STATUS.md and yield pending tasks as (task_id, description)."""
    import re
    if not os.path.exists(status_path):
        return []
    with open(status_path, 'r') as f:
        content = f.read()
    # Find pending checklist items: - [ ] task-XXX: description
    pattern = r"^- \[\s\]\s+(task-\d+):\s+(.+?)(?:\n|$)"
    matches = re.findall(pattern, content, re.MULTILINE)
    tasks = []
    for task_id, desc in matches:
        tasks.append((task_id.strip(), desc.strip()))
    return tasks


def run_all_pending_tasks():
    """Read STATUS.md, run the orchestrator for each pending task."""
    tasks = parse_status_file()
    if not tasks:
        print("No pending tasks found in STATUS.md")
        return
    for task_id, description in tasks:
        print(f"\n=== Running task {task_id}: {description} ===")
        run_id = task_id  # use task_id as run_id for trace correlation
        initial_state = {
            "task_id": run_id,
            "issue_text": description,
            "messages": []
        }
        try:
            result = agency_orchestrator.invoke(initial_state)
            print(f"Task {task_id} completed successfully.")
            # Optionally update STATUS.md to mark as done - left to external script
        except Exception as e:
            print(f"Task {task_id} failed with error: {e}")
            # In a real system, we would update STATUS.md to reflect failure


if __name__ == "__main__":
    # When run directly, process all pending tasks in STATUS.md
    run_all_pending_tasks()