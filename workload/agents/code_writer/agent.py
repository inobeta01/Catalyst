"""Code writer agent: receives a task from triage and produces or patches code.
It works in three steps:
1️⃣ **fetch_task** – pulls the high‑level description and any existing source files from the MCP cache.
2️⃣ **generate_patch** – uses a capable LLM (Claude 3.5 Sonnet) to produce a code snippet or diff.
3️⃣ **apply_patch** – writes the generated file(s) to the repository and records the result back into the MCP cache.

The agent is deliberately lightweight; it does not perform static analysis itself – that is left to the existing `run_code_analysis` tool for later stages if needed.
"""

from langgraph.graph import StateGraph
from typing import TypedDict, Optional, List, Annotated
from langgraph.graph.message import add_messages

import json
from workload.prompts.code_writer import CODE_WRITER_PROMPT
from workload.llm import safe_llm_call
from workload.tools import fetch_issue_context
from workload.tools.mcp import MCP  # shared cache implementation

class CodeWriterState(TypedDict):
    messages: Annotated[List, add_messages]
    issue_id: Optional[str]
    description: Optional[str]
    generated_code: Optional[dict]  # {"path": "relative/file.py", "content": "..."}
    trace_span_kind: Optional[str]


def fetch_task(state: CodeWriterState) -> CodeWriterState:
    """Step 1 – pull the task description from the shared MCP cache.

    The triage agent stores its final classification under the key
    ``triage_result``; we read it here. If the cache is empty we fall back to a
    generic placeholder so the agent still runs (useful for manual testing).
    """
    issue_id = state.get("issue_id", "unknown")
    # Use a dedicated MCP instance scoped to this run (the task_id can be the
    # issue_id or any UUID the orchestrator provides).  For simplicity we reuse
    # the issue_id.
    with MCP(task_id=issue_id) as cache:
        triage_result = cache.get("triage_result")
    description = triage_result.get("description") if isinstance(triage_result, dict) else "Fix the reported issue"
    return {**state, "description": description, "trace_span_kind": "code_writer.fetch_task"}


def generate_patch(state: CodeWriterState) -> CodeWriterState:
    """Step 2 – ask an LLM to produce the code needed for the description.

    The prompt asks for a **single file** with its relative path and full
    content.  The LLM response is expected to be a JSON object:

    ```json
    {"path": "module/file.py", "content": "..."}
    ```
    """
    description = state.get("description", "")
    prompt = f"{CODE_WRITER_PROMPT}\n\nTask description:\n{description}\n\nRespond with a JSON object containing the target file path (relative to the repository root) and the complete file content."
    result = safe_llm_call(prompt, system_prompt=CODE_WRITER_PROMPT, model_name="claude-3-5-sonnet")
    try:
        generated = json.loads(result)
    except Exception as exc:
        # If parsing fails we store the raw LLM output for debugging.
        generated = {"path": "debug_output.txt", "content": result}
    return {**state, "generated_code": generated, "trace_span_kind": "code_writer.generate_patch"}


def apply_patch(state: CodeWriterState) -> CodeWriterState:
    """Step 3 – write the generated file to disk and record it in the MCP cache.

    The repository root is the current working directory (the orchestrator runs
    from the project root).  After writing we store the same payload under the
    key ``code_writer_result`` so downstream agents can read it.
    """
    payload = state.get("generated_code", {})
    if not payload:
        return {**state, "trace_span_kind": "code_writer.apply_patch"}
    path = payload.get("path")
    content = payload.get("content", "")
    if path:
        # Ensure parent directories exist.
        import os, pathlib
        full_path = pathlib.Path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    # Write back to MCP for visibility.
    issue_id = state.get("issue_id", "unknown")
    with MCP(task_id=issue_id) as cache:
        cache.set("code_writer_result", payload)
    return {**state, "trace_span_kind": "code_writer.apply_patch"}


def build_code_writer_agent():
    graph = StateGraph(CodeWriterState)
    graph.add_node("fetch", fetch_task)
    graph.add_node("generate", generate_patch)
    graph.add_node("apply", apply_patch)
    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "generate")
    graph.add_edge("generate", "apply")
    graph.set_finish_point("apply")
    return graph.compile()

# Exported compiled agent ready for the orchestration layer.
agent = build_code_writer_agent()
