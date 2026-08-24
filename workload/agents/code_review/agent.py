"""Code review agent: performs multi-step PR review with tool calls and multi‑LLM reasoning via FreeLLM API.
"""
from langgraph.graph import StateGraph
from typing import TypedDict, Optional, List, Annotated
from langgraph.graph.message import add_messages
from workload.prompts.code_review import CODE_REVIEW_PROMPT
from workload.llm import safe_llm_call
from workload.tools import fetch_pr_data, run_code_analysis

class CodeReviewState(TypedDict):
    messages: Annotated[List, add_messages]
    pr_id: Optional[str]
    pr_description: Optional[str]
    diffs: Optional[List[str]]
    chunk_reviews: Optional[List[dict]]
    final_verdict: Optional[str]
    trace_span_kind: Optional[str]

def fetch_pr(state: CodeReviewState) -> CodeReviewState:
    """Step 1 – Get PR metadata and raw diffs via a tool call."""
    pr_id = state.get("pr_id", "unknown")
    data = fetch_pr_data(pr_id)
    return {
        **state,
        "pr_description": data.get("title"),
        "diffs": data.get("diff_chunks"),
        "trace_span_kind": "code_review.fetch_pr",
    }

def review_chunks(state: CodeReviewState) -> CodeReviewState:
    """Step 2 – Review each diff chunk with a dedicated LLM (Claude 3.5 Sonnet).
    Each chunk can also invoke a static analysis tool for deeper insight.
    """
    diffs = state.get("diffs", [])
    chunk_reviews = []
    for chunk in diffs:
        # Run static analysis first.
        analysis = run_code_analysis(chunk)
        # Build LLM prompt.
        prompt = (
            f"You are reviewing a code change chunk.\n\n"
            f"Chunk:\n{chunk}\n\n"
            f"Static analysis findings: {analysis.get('potential_issues')}\n\n"
            "Provide a concise review comment (max 2 sentences) and give a severity level (info, warning, error)."
        )
        review = safe_llm_call(prompt, system_prompt=CODE_REVIEW_PROMPT, model_name="claude-3-5-sonnet")
        chunk_reviews.append({
            "chunk": chunk,
            "analysis": analysis,
            "review": review.strip(),
        })
    return {**state, "chunk_reviews": chunk_reviews, "trace_span_kind": "code_review.review_chunks"}

def aggregate_review(state: CodeReviewState) -> CodeReviewState:
    """Step 3 – Aggregate chunk reviews into a final verdict using a higher‑capacity model.
    Uses the "fusion" model that fuses multiple LLM outputs.
    """
    chunk_reviews = state.get("chunk_reviews", [])
    combined = "\n---\n".join([cr["review"] for cr in chunk_reviews])
    prompt = (
        f"You are summarizing a PR review composed of multiple chunk comments.\n\n"
        f"Chunk reviews:\n{combined}\n\n"
        "Summarize the overall health of the PR, list any critical blockers, and output a final verdict string: \"approve\", \"request-changes\", or \"comment\"."
    )
    verdict = safe_llm_call(prompt, system_prompt=CODE_REVIEW_PROMPT, model_name="fusion")
    return {**state, "final_verdict": verdict.strip(), "trace_span_kind": "code_review.aggregate"}

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
