"""Templates for high-intensity orchestration tasks and failure simulation mappings.
"""

TASK_TEMPLATES = {
    "task-101": {
        "description": "Implement a high-performance distributed scraper for 500+ URLs with JS rendering.",
        "failure_mode": "agent_crash",
        "env_var": "AGENT_FAIL",
        "target_trace": "Observe AgentOps recovery/cleanup of 10+ worker threads."
    },
    "task-102": {
        "description": "Refactor Catalyst Core to use Asynchronous I/O and migrate 50+ blocking calls.",
        "failure_mode": "plugin_build_error",
        "env_var": "PLUGIN_BUILD_ERR",
        "target_trace": "Capture massive stack traces during complex compilation/dependency resolution."
    },
    "task-103": {
        "description": "Design and execute a 20-node LangGraph workflow for automated multi-repo CI/CD.",
        "failure_mode": "workflow_exception",
        "env_var": "LANGGRAPH_ERR",
        "target_trace": "Analyze Phoenix graph state-bloat and exception propagation across nodes."
    },
    "task-104": {
        "description": "Synchronize 10,000 records across 5 external SaaS APIs (Stripe, Salesforce, etc.).",
        "failure_mode": "network_timeout",
        "env_var": "HTTP_TIMEOUT",
        "target_trace": "Inspect retry logic, backoff curves, and partial state synchronization traces."
    },
    "task-105": {
        "description": "Perform a full-codebase security audit and auto-fix 200+ linting/security issues.",
        "failure_mode": "partial_success",
        "env_var": "PARTIAL_SUCCESS",
        "target_trace": "Compare 'Proposed' vs 'Applied' changes in traces when only a subset succeeds."
    }
}

def get_task_by_id(task_id: str) -> dict:
    return TASK_TEMPLATES.get(task_id, {})

def get_failure_config(task_id: str) -> dict:
    task = get_task_by_id(task_id)
    if not task:
        return {}
    return {
        "failure_mode": task["failure_mode"],
        "env_var": task["env_var"]
    }
