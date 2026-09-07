"""Code review agent: review a PR diff end-to-end.

Three LangGraph nodes, each backed by a concrete Gemini model:

    fetch_pr -> review_chunks -> aggregate_review

Step contracts:
- ``fetch_pr``        : tool call, no LLM
- ``review_chunks``   (gemini-1.5-pro):  one review per diff chunk, severity-tagged
- ``aggregate_review``(gemini-1.5-pro):  final verdict + blocker list
"""
import re
from typing import Annotated, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from workload.llm import safe_llm_call
from workload.prompts.code_review import CODE_REVIEW_PROMPT
from workload.tools import fetch_pr_data, run_code_analysis


_SEVERITY_RE = re.compile(r"\b(info|warning|error)\b", re.IGNORECASE)
_VERDICT_RE = re.compile(r"\b(approve|request-changes|comment)\b", re.IGNORECASE)


class CodeReviewState(TypedDict):
    messages: Annotated[List, add_messages]
    pr_id: Optional[str]
    pr_description: Optional[str]
    diffs: Optional[List[str]]
    chunk_reviews: Optional[List[Dict]]
    final_verdict: Optional[str]
    blocker_count: Optional[int]
    trace_span_kind: Optional[str]


_CHUNK_PROMPT = (
    "Review this diff chunk. Reply with exactly three lines:\n"
    "Severity: <info|warning|error>\n"
    "Comment: <one sentence, max 25 words>\n"
    "Confidence: <low|medium|high>\n\n"
    "Diff chunk:\n{chunk}\n\n"
    "Static analysis findings:\n{findings}\n"
)


_AGGREGATE_PROMPT = (
    "Summarize the per-chunk PR reviews below. Reply with exactly four lines:\n"
    "Verdict: <approve|request-changes|comment>\n"
    "Blockers: <integer count of severity=error chunks>\n"
    "Highlights: <one sentence>\n"
    "Action: <single concrete next step, max 15 words>\n\n"
    "Chunk reviews:\n{reviews}\n"
)


def _extract_severity(text: str) -> str:
    match = _SEVERITY_RE.search(text)
    return match.group(1).lower() if match else "info"


def _extract_verdict(text: str) -> str:
    match = _VERDICT_RE.search(text)
    return match.group(1).lower() if match else "comment"


def fetch_pr(state: CodeReviewState) -> CodeReviewState:
    """Step 1 — fetch PR metadata + diff chunks via the PR tool."""
    pr_id = state.get("pr_id", "unknown")
    data = fetch_pr_data(pr_id)
    return {
        **state,
        "pr_description": data.get("title"),
        "diffs": data.get("diff_chunks") or [],
        "trace_span_kind": "code_review.fetch_pr",
    }


def review_chunks(state: CodeReviewState) -> CodeReviewState:
    """Step 2 — gemini-1.5-pro reviews each diff chunk with static analysis."""
    diffs = state.get("diffs", [])
    chunk_reviews: List[Dict] = []

    for chunk in diffs:
        analysis = run_code_analysis(chunk)
        prompt = _CHUNK_PROMPT.format(
            chunk=chunk,
            findings=analysis.get("potential_issues", "(none)"),
        )
        review_text = safe_llm_call(
            prompt,
            system_prompt=CODE_REVIEW_PROMPT,
            model_name="gemini-pro",
            temperature=0.2,
            max_output_tokens=256,
        )
        chunk_reviews.append({
            "chunk": chunk,
            "analysis": analysis,
            "review": review_text,
            "severity": _extract_severity(review_text),
        })

    return {
        **state,
        "chunk_reviews": chunk_reviews,
        "trace_span_kind": "code_review.review_chunks",
    }


def aggregate_review(state: CodeReviewState) -> CodeReviewState:
    """Step 3 — gemini-1.5-pro fuses the per-chunk reviews into a verdict."""
    chunk_reviews = state.get("chunk_reviews", [])
    combined = "\n---\n".join(cr["review"] for cr in chunk_reviews)
    prompt = _AGGREGATE_PROMPT.format(reviews=combined or "(no reviews)")

    verdict_text = safe_llm_call(
        prompt,
        system_prompt=CODE_REVIEW_PROMPT,
        model_name="gemini-pro",
        temperature=0.2,
        max_output_tokens=512,
    )

    # Independent ground-truth blocker count from the per-chunk severities.
    ground_truth_blockers = sum(
        1 for cr in chunk_reviews if cr.get("severity") == "error"
    )

    return {
        **state,
        "final_verdict": _extract_verdict(verdict_text),
        "blocker_count": ground_truth_blockers,
        "trace_span_kind": "code_review.aggregate",
    }


def build_code_review_agent():
    graph = StateGraph(CodeReviewState)
    graph.add_node("fetch", fetch_pr)
    graph.add_node("review", review_chunks)
    graph.add_node("aggregate", aggregate_review)
    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "review")
    graph.add_edge("review", "aggregate")
    graph.set_finish_point("aggregate")
    return graph.compile()


agent = build_code_review_agent()
create_agent = agent
