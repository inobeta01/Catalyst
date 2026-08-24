"""Workload tools for agent interactions (stubbed/simulated interface, ready for sandbox stage 3)."""

def fetch_issue_context(issue_id: str) -> dict:
    """Tool: fetch full context, logs, and stack trace for an issue."""
    return {
        "issue_id": issue_id,
        "logs": "ERROR 2026-08-24 10:14:02 [main] NullPointerException at Service.java:42",
        "author": "dev-user-41",
        "affected_services": ["auth-service", "user-api"],
        "recent_deploy_commit": "a3f8c92b",
    }


def fetch_pr_data(pr_id: str) -> dict:
    """Tool: fetch PR metadata and code diffs."""
    return {
        "pr_id": pr_id,
        "title": "Fix null pointer in auth token validation",
        "author": "contributor-12",
        "diff_chunks": [
            "@@ -40,6 +40,8 @@ public void validateToken(String token) {\n+    if (token == null) {\n+        throw new IllegalArgumentException(\"Token cannot be null\");\n+    }",
            "@@ -102,4 +104,3 @@ public User parseUser(String payload) {\n-    return mapper.readValue(payload, User.class);\n+    return payload != null ? mapper.readValue(payload, User.class) : null;"
        ]
    }


def run_code_analysis(code_chunk: str) -> dict:
    """Tool: static analysis / security check on a code diff chunk."""
    has_null_check = "null" in code_chunk
    return {
        "chunk_analyzed": code_chunk[:30] + "...",
        "potential_issues": [] if has_null_check else ["Missing null check or boundary check"],
        "static_analysis_pass": True,
    }


def fetch_referenced_docs(doc_refs: list[str]) -> dict:
    """Tool: fetch content of referenced documentation or specification files."""
    docs_content = {}
    for ref in doc_refs:
        docs_content[ref] = f"Content specification for doc reference {ref}: Standard agency SLA & architecture rules."
    return docs_content
