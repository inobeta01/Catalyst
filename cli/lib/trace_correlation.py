"""Trace correlation: maps run_id → trace_id → failure_mode."""

from typing import Dict, Optional


class TraceCorrelator:
    """Correlate LangSmith run IDs with Phoenix trace IDs and failure modes."""

    def __init__(self):
        self._run_to_trace: Dict[str, str] = {}
        self._trace_to_failure: Dict[str, Optional[str]] = {}

    def register_run(self, run_id: str, trace_id: str, failure_mode: Optional[str] = None):
        """Register a run-to-trace mapping."""
        self._run_to_trace[run_id] = trace_id
        self._trace_to_failure[trace_id] = failure_mode

    def trace_id(self, run_id: str) -> Optional[str]:
        """Get trace ID for a run ID."""
        return self._run_to_trace.get(run_id)

    def failure_mode(self, trace_id: str) -> Optional[str]:
        """Get failure mode for a trace ID."""
        return self._trace_to_failure.get(trace_id)
