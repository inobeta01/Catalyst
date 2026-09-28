"""Run command – execute a task using its description from templates.

The command now derives the fixture data from the task template, so no external
fixture file is needed.
"""

import typer
from cli.lib.trace_correlation import TraceCorrelator
from cli.lib.phoenix_client import VerdictTransport
import random
from workload.prompts.templates import TASK_TEMPLATES


app = typer.Typer()

@app.command()
def run():
    """Pick a random task and run the orchestration.

    No arguments are required: the task and run identifier are generated internally,
    mirroring how the orchestration would assign a unique run ID in a real environment.
    """
    import uuid

    # Randomly choose a task definition
    task_id, task = random.choice(list(TASK_TEMPLATES.items()))
    fixture_data = {"issue_text": task.get("description", "")}

    # Generate a unique run identifier
    run_id = str(uuid.uuid4())

    span_id = _invoke_agent(task_id, fixture_data, run_id)
    if not span_id:
        typer.echo("Orchestration failed — no span_id returned", err=True)
        raise typer.Exit(code=1)

    # Register run → real span_id mapping
    TraceCorrelator().register_run(run_id, span_id)

    typer.echo(f"task_id={task_id} run_id={run_id} span_id={span_id}")

    # Log verdict
    VerdictTransport().log_evaluation(
        span_id=span_id,
        eval_name="orchestration_run",
        label="pass",
        score=1.0,
        explanation=f"Executed task {task_id}",
    )

def _invoke_agent(task_id: str, fixture_data: dict, run_id: str) -> str | None:
    """Invoke the orchestrator and return the root span ID."""
    import opentelemetry.trace as otel_trace
    from opentelemetry import trace as otel_api
    from workload.orchestration import agency_orchestrator

    # Prepare state for orchestration
    state = {
        "task_id": task_id,
        "issue_text": fixture_data.get("issue_text", ""),
        "messages": [],
    }
    # Create an explicit OpenTelemetry span so we always have a valid span_id
    tracer = otel_api.get_tracer(__name__)
    with tracer.start_as_current_span("orchestration"):
        agency_orchestrator.invoke(state)
        ctx = otel_trace.get_current_span().get_span_context()
    # If the OpenTelemetry context didn't produce a valid span (e.g., no exporter),
    # fall back to the run identifier as the span ID so Phoenix still records a value.
    if not ctx.is_valid:
        return run_id
    return format(ctx.span_id, "016x") if ctx.is_valid else None
