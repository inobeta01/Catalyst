"""Unit tests for TraceCorrelator."""

from cli.lib.trace_correlation import TraceCorrelator


def test_register_and_lookup():
    c = TraceCorrelator()
    c.register_run("run-1", "trace-abc", failure_mode="retry-storms")
    assert c.trace_id("run-1") == "trace-abc"
    assert c.failure_mode("trace-abc") == "retry-storms"


def test_missing_run():
    c = TraceCorrelator()
    assert c.trace_id("unknown") is None
    assert c.failure_mode("unknown") is None
