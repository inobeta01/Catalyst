"""Code writer agent: receives a task from triage and produces or patches code.

Three LangGraph nodes, each backed by a concrete Gemini model:

    fetch_task -> generate_patch -> apply_patch

Step contracts:
- ``fetch_task``:    MCP read, no LLM
- ``generate_patch``(gemini-1.5-pro): produces a single file as JSON
- ``apply_patch``:   writes the file + records it in MCP, no LLM
"""

import json
import pathlib
from typing import Annotated, List, Optional, TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from workload.llm import safe_llm_call
from workload.prompts.code_writer import CODE_WRITER_PROMPT
from workload.tools.mcp import MCP  # shared cache implementation


class CodeWriterState(TypedDict):
    messages: Annotated[List, add_messages]
    issue_id: Optional[str]
    description: Optional[str]
    generated_code: Optional[dict]  # {"path": "relative/file.py", "content": "..."}
    trace_span_kind: Optional[str]


def fetch_task(state: CodeWriterState) -> CodeWriterState:
    """Step 1 — pull the task description from the shared MCP cache.

    The triage agent stores its final classification under ``triage_result``;
    we read it here.  If the cache is empty we fall back to a placeholder so
    the agent still runs (useful for manual testing).
    """
    issue_id = state.get("issue_id", "unknown")
    with MCP(task_id=issue_id) as cache:
        triage_result = cache.get("triage_result")
    description = (
        triage_result.get("description")
        if isinstance(triage_result, dict)
        else "Fix the reported issue"
    )
    return {
        **state,
        "description": description,
        "trace_span_kind": "code_writer.fetch_task",
    }


_GENERATE_PROMPT = (
    "Produce a single-file code patch that satisfies the task below.\n"
    "Respond with one JSON object and nothing else:\n"
    '{{"path": "<relative file path, e.g. module/file.py>", '
    '"content": "<complete file contents as a JSON string>"}}\n\n'
    "Task:\n{description}\n"
)


def _try_parse_json(text: str) -> Optional[dict]:
    """Pull the first JSON object out of a model response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Some models wrap JSON in ```json fences; strip them and retry.
    if "```" in text:
        fenced = text.split("```", 2)
        if len(fenced) >= 3:
            inner = fenced[1].lstrip("json").strip() if fenced[1].lstrip().startswith("json") else fenced[1]
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                pass
    # Last resort: take the substring between the first { and the last }.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def generate_patch(state: CodeWriterState) -> CodeWriterState:
    """Step 2 — gemini-1.5-pro emits a single-file patch as JSON."""
    description = state.get("description", "")
    prompt = _GENERATE_PROMPT.format(description=description)

    result_text = safe_llm_call(
        prompt,
        system_prompt=CODE_WRITER_PROMPT,
        model_name="gemini-pro",
        temperature=0.2,
        max_output_tokens=2048,
    )
    parsed = _try_parse_json(result_text)
    if parsed is None:
        parsed = {"path": "debug_output.txt", "content": result_text}
    return {
        **state,
        "generated_code": parsed,
        "trace_span_kind": "code_writer.generate_patch",
    }


def apply_patch(state: CodeWriterState) -> CodeWriterState:
    """Step 3 — write the file to disk and record it in MCP."""
    payload = state.get("generated_code") or {}
    path = payload.get("path") if isinstance(payload, dict) else None
    content = payload.get("content", "") if isinstance(payload, dict) else ""

    if path:
        full_path = pathlib.Path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    issue_id = state.get("issue_id", "unknown")
    with MCP(task_id=issue_id) as cache:
        cache.set("code_writer_result", payload)

    return {
        **state,
        "trace_span_kind": "code_writer.apply_patch",
    }


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
