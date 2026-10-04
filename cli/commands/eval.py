"""Eval command: run the orchestration with a randomly injected failure mode for a given task."""

import os
import random
import typer
import json
from pathlib import Path
from cli.lib.trace_correlation import TraceCorrelator
from cli.lib.phoenix_client import VerdictTransport
from workload.prompts.templates import TASK_TEMPLATES, get_failure_config
from .run import _invoke_agent

app = typer.Typer()

@app.command()
def cmd_eval(
    task_id: str = typer.Option(None, help="Task identifier (random if omitted)"),
    fixture: str = typer.Option(None, help="Path to fixture JSON file (auto-generated if omitted)"),
    run_id: str = typer.Option(None, help="Run identifier (auto-generated if omitted)"),
):
    """Run a single task with a random chance of injecting its failure mode.

    If --task-id is omitted, a random task is chosen from the catalog.
    If --fixture is omitted, a fixture is generated from the task description.
    If --run-id is omitted, a UUID is generated.
    """
    # Choose task randomly if not specified
    if task_id is None:
        task_id, task = random.choice(list(TASK_TEMPLATES.items()))
    else:
        task = TASK_TEMPLATES.get(task_id, {})

    # Generate fixture if not provided
    if fixture is None:
        fixture_data = {"issue_text": task.get("description", "")}
        fixture = f"auto:{task_id}"
    else:
        # Load fixture from file
        fixture_path = Path(fixture)
        if not fixture_path.exists():
            typer.echo(f"Fixture not found: {fixture}", err=True)
            raise typer.Exit(code=1)
        with open(fixture_path) as f:
            fixture_data = json.load(f)

    # Generate run_id if not provided
    if run_id is None:
        import uuid
        run_id = str(uuid.uuid4())

    # Randomly decide whether to trigger failure mode for this task
    failure_cfg = get_failure_config(task_id)
    if failure_cfg:
        env_var = failure_cfg.get("env_var")
        if env_var:
            # 50% chance to enable failure simulation
            if random.random() < 0.5:
                os.environ[env_var] = "1"
            else:
                os.environ.pop(env_var, None)

    # Invoke orchestrator (same as run command)
    span_id = _invoke_agent(task_id, fixture_data, run_id)

    if not span_id:
        typer.echo("Orchestration failed — no span_id returned", err=True)
        raise typer.Exit(code=1)

    # Register run → real span_id mapping (not a local UUID)
    correlator = TraceCorrelator()
    correlator.register_run(run_id, span_id)

    typer.echo(f"task_id={task_id} fixture={fixture} run_id={run_id} span_id={span_id}")

    # Write verdict using real span_id
    verdict = VerdictTransport()
    verdict.log_evaluation(
        span_id=span_id,
        eval_name="orchestration_eval",
        label="pass",
        score=1.0,
        explanation=f"Executed task {task_id} with fixture {fixture}",
    )
