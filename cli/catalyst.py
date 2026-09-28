"""Catalyst CLI entrypoint using Typer for subcommands."""

import typer
from cli.commands.run import run as run_command
from cli.commands.reset import cmd_reset
from cli.commands.eval import cmd_eval
from cli.commands.feed import feed as feed_command

cli = typer.Typer(add_completion=False)

# Detailed command registration

cli.command(name="run", help=(
    "Execute a random task against the orchestration.\n\n"
    "A task is chosen at random from the built‑in catalog (see `workload/prompts/templates.py`). "
    "The task description becomes the issue text for the triage agent, which routes the work to the "
    "appropriate downstream agent. No arguments are required; a unique run identifier is generated internally."
))(run_command)

cli.command(name="feed", help=(
    "Manage the task catalog that drives `run` and `eval`.\n\n"
    "Use one of three modes:\n"
    "  • rewrite – replace the entire catalog with a JSON source.\n"
    "  • append  – merge new tasks from a JSON source into the catalog.\n"
    "  • clear   – empty the catalog.\n\n"
    "Provide the JSON source via --source (ignored for `clear`). Each entry must contain at least: description, failure_mode, env_var."
))(feed_command)

@cli.command(name="reset", help=(
    "Reset Catalyst to a clean state.\n\n"
    "Clears Phoenix traces, AgentOps sessions, and any cached fixtures. Safe to run between experiments."
))
def reset():
    cmd_reset()

@cli.command(name="eval", help=(
    "Run a single task with a random chance of injecting its failure mode.\n\n"
    "Specify --task-id, --fixture, and --run-id to run a specific task with a fixture."
))
def eval(
    task_id: str = typer.Option(..., help="Task identifier"),
    fixture: str = typer.Option(..., help="Path to fixture JSON file"),
    run_id: str = typer.Option(..., help="Run identifier"),
):
    cmd_eval(task_id=task_id, fixture=fixture, run_id=run_id)

def main():
    cli()
