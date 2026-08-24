"""Brief writer agent: multi‑step brief drafting using LLMs, tool calls, and FreeLLM API.
"""
from langgraph.graph import StateGraph
from typing import TypedDict, Optional, List, Annotated
from langgraph.graph.message import add_messages
from workload.prompts.brief_writer import BRIEF_WRITER_PROMPT
from workload.llm import safe_llm_call
from workload.tools import fetch_referenced_docs

class BriefWriterState(TypedDict):
    messages: Annotated[List, add_messages]
    requirements: Optional[str]
    outline: Optional[str]
    doc_refs: Optional[List[str]]
    fetched_docs: Optional[dict]
    sections: Optional[dict]
    final_brief: Optional[str]
    trace_span_kind: Optional[str]

def outline_structure(state: BriefWriterState) -> BriefWriterState:
    """Step 1 – LLM outlines the brief structure.
    Uses a lightweight model for fast brainstorming.
    """
    req = state.get("requirements", "")
    prompt = f"Given the following requirements, outline a technical brief with section headings.\n\n{req}"
    outline = safe_llm_call(prompt, system_prompt=BRIEF_WRITER_PROMPT, model_name="auto:fast")
    return {**state, "outline": outline.strip(), "trace_span_kind": "brief_writer.outline"}

def fetch_docs(state: BriefWriterState) -> BriefWriterState:
    """Step 2 – Pull referenced documentation via tool call.
    The outline may embed references like [DOC-123]; we parse and fetch them.
    """
    outline = state.get("outline", "")
    # Very simple parser: collect tokens that look like DOC-<id>
    refs = [tok for tok in outline.split() if tok.startswith("DOC-")]
    docs = fetch_referenced_docs(refs)
    return {**state, "doc_refs": refs, "fetched_docs": docs, "trace_span_kind": "brief_writer.fetch_docs"}

def draft_sections(state: BriefWriterState) -> BriefWriterState:
    """Step 3 – Draft each section with a stronger LLM (Claude 3.5 Sonnet)."""
    outline = state.get("outline", "")
    docs = state.get("fetched_docs", {})
    # Split outline into headings (naïve split by newline)
    sections = {}
    for heading in outline.split("\n"):
        heading = heading.strip()
        if not heading:
            continue
        # Build prompt using any fetched doc snippets relevant to the heading.
        doc_snippets = " ".join(docs.values())
        prompt = (
            f"Write the content for the brief section titled '{heading}'.\n"
            f"Use the following extracted documentation as reference: {doc_snippets}\n"
        )
        content = safe_llm_call(prompt, system_prompt=BRIEF_WRITER_PROMPT, model_name="claude-3-5-sonnet")
        sections[heading] = content.strip()
    return {**state, "sections": sections, "trace_span_kind": "brief_writer.draft"}

def assemble_brief(state: BriefWriterState) -> BriefWriterState:
    """Step 4 – Assemble all sections into the final brief using a fusion model.
    The fusion model can reconcile any inconsistencies.
    """
    sections = state.get("sections", {})
    assembled = "\n\n".join([f"## {h}\n{c}" for h, c in sections.items()])
    # Optional final polishing step with a different LLM.
    prompt = f"Polish the following technical brief for style and conciseness.\n\n{assembled}"
    polished = safe_llm_call(prompt, system_prompt=BRIEF_WRITER_PROMPT, model_name="fusion")
    return {**state, "final_brief": polished.strip(), "trace_span_kind": "brief_writer.assemble"}

def build_brief_writer_agent():
    graph = StateGraph(BriefWriterState)
    graph.add_node("outline", outline_structure)
    graph.add_node("fetch", fetch_docs)
    graph.add_node("draft", draft_sections)
    graph.add_node("assemble", assemble_brief)
    graph.set_entry_point("outline")
    graph.add_edge("outline", "fetch")
    graph.add_edge("fetch", "draft")
    graph.add_edge("draft", "assemble")
    graph.set_finish_point("assemble")
    return graph.compile()

agent = build_brief_writer_agent()
