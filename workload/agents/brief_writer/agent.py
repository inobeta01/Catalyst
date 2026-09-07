"""Brief writer agent: turns a requirements blurb into a structured technical brief.

Four LangGraph nodes, each backed by a concrete Gemini model:

    outline -> fetch -> draft -> assemble

Step contracts:
- ``outline``  (gemini-1.5-flash):    5-9 markdown headings, each inline-anchored
- ``fetch``:                          parses [DOC-id] tokens, no LLM
- ``draft``    (gemini-1.5-pro):      one section per heading, in order
- ``assemble`` (gemini-1.5-pro):      final style/conciseness pass
"""
import re
from typing import Annotated, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from workload.llm import safe_llm_call
from workload.prompts.brief_writer import BRIEF_WRITER_PROMPT
from workload.tools import fetch_referenced_docs


_DOC_TOKEN_RE = re.compile(r"\[DOC-([A-Za-z0-9_\-]+)\]")


class BriefWriterState(TypedDict):
    messages: Annotated[List, add_messages]
    requirements: Optional[str]
    outline: Optional[str]
    doc_refs: Optional[List[str]]
    fetched_docs: Optional[Dict[str, str]]
    sections: Optional[Dict[str, str]]
    final_brief: Optional[str]
    trace_span_kind: Optional[str]


_OUTLINE_PROMPT = (
    "Produce a markdown outline of 5 to 9 section headings for a technical brief\n"
    "that satisfies the requirements below. One heading per line, no body text.\n"
    "When a heading refers to a document, cite it inline as [DOC-<id>].\n\n"
    "Requirements:\n{requirements}\n"
)


_DRAFT_PROMPT = (
    "Write the content for brief section '{heading}'.\n"
    "Length: 3-6 sentences. Cite referenced documents inline as [DOC-<id>].\n"
    "Use the following extracted documentation snippets as factual reference:\n"
    "{docs}\n"
)


_ASSEMBLE_PROMPT = (
    "Polish the technical brief below for style and conciseness. Preserve all\n"
    "section headings and [DOC-<id>] citations verbatim. Output only the polished\n"
    "brief, no preamble.\n\n"
    "{brief}\n"
)


def outline_structure(state: BriefWriterState) -> BriefWriterState:
    """Step 1 — gemini-1.5-flash produces a heading-only outline."""
    requirements = state.get("requirements", "")
    prompt = _OUTLINE_PROMPT.format(requirements=requirements)
    outline = safe_llm_call(
        prompt,
        system_prompt=BRIEF_WRITER_PROMPT,
        model_name="gemini-fast",
        temperature=0.3,
        max_output_tokens=512,
    )
    return {
        **state,
        "outline": outline,
        "trace_span_kind": "brief_writer.outline",
    }


def fetch_docs(state: BriefWriterState) -> BriefWriterState:
    """Step 2 — pull every [DOC-id] referenced in the outline."""
    outline = state.get("outline", "")
    refs = _DOC_TOKEN_RE.findall(outline)
    refs = [f"DOC-{r}" for r in refs]
    docs = fetch_referenced_docs(refs) if refs else {}
    return {
        **state,
        "doc_refs": refs,
        "fetched_docs": docs,
        "trace_span_kind": "brief_writer.fetch_docs",
    }


def draft_sections(state: BriefWriterState) -> BriefWriterState:
    """Step 3 — gemini-1.5-pro drafts one body per heading."""
    outline = state.get("outline", "")
    docs = state.get("fetched_docs", {})
    headings = [line.strip() for line in outline.splitlines() if line.strip()]

    sections: Dict[str, str] = {}
    for heading in headings:
        # Inline-cited docs land here as the only factual source.
        referenced = [
            token for token in heading.split() if token.startswith("[DOC-")
        ]
        snippets = " ".join(docs.get(token.strip("[]"), "") for token in referenced)
        prompt = _DRAFT_PROMPT.format(heading=heading, docs=snippets or "(no referenced docs)")
        content = safe_llm_call(
            prompt,
            system_prompt=BRIEF_WRITER_PROMPT,
            model_name="gemini-pro",
            temperature=0.5,
            max_output_tokens=512,
        )
        sections[heading] = content

    return {
        **state,
        "sections": sections,
        "trace_span_kind": "brief_writer.draft",
    }


def assemble_brief(state: BriefWriterState) -> BriefWriterState:
    """Step 4 — gemini-1.5-pro polishes the assembled brief."""
    sections = state.get("sections", {})
    assembled = "\n\n".join(f"## {h}\n{c}" for h, c in sections.items())
    prompt = _ASSEMBLE_PROMPT.format(brief=assembled)
    polished = safe_llm_call(
        prompt,
        system_prompt=BRIEF_WRITER_PROMPT,
        model_name="gemini-pro",
        temperature=0.4,
        max_output_tokens=2048,
    )
    return {
        **state,
        "final_brief": polished,
        "trace_span_kind": "brief_writer.assemble",
    }


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
create_agent = agent
