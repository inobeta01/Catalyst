"""Feed command – manipulate the TASK_TEMPLATES file.

Options:
  --mode rewrite   Replace the entire templates file with the contents of <source>.
  --mode append    Append new task definitions from <source> to the existing file.
  --mode clear     Remove all entries (reset to empty dict).

<source> should be a JSON file containing a dict of task IDs to definitions.
"""

import typer
import json
from pathlib import Path

app = typer.Typer()

TEMPLATE_PATH = Path(__file__).parents[2] / "workload" / "prompts" / "templates.py"

def _load_source(source: Path) -> dict:
    with open(source) as f:
        return json.load(f)

@app.command()
def feed(
    mode: str = typer.Option(..., "--mode", help="rewrite | append | clear"),
    source: Path = typer.Option(None, "--source", exists=True, file_okay=True, dir_okay=False, help="Path to JSON file with task definitions"),
):
    """Rewrite, append, or clear the TASK_TEMPLATES module.

    The operation modifies the Python file in‑place while preserving the surrounding
    docstring. For simplicity we embed the supplied JSON as a Python dict literal.
    """
    if mode not in {"rewrite", "append", "clear"}:
        typer.echo(f"Invalid mode: {mode}", err=True)
        raise typer.Exit(code=1)

    # Read the existing file
    with open(TEMPLATE_PATH) as f:
        lines = f.readlines()

    # Find the start and end of the TASK_TEMPLATES dict literal
    start, end = None, None
    for i, line in enumerate(lines):
        if line.strip().startswith("TASK_TEMPLATES = {"):
            start = i
        if start is not None and line.strip().endswith("}\n"):
            end = i
            break
    if start is None or end is None:
        typer.echo("Could not locate TASK_TEMPLATES dict in file", err=True)
        raise typer.Exit(code=1)

    if mode == "clear":
        new_dict = {}
    else:
        new_entries = _load_source(source)
        if mode == "rewrite":
            new_dict = new_entries
        else:  # append
            # Load existing dict
            existing_code = "".join(lines[start + 1 : end])
            existing_dict = eval("{" + existing_code + "}")  # safe because file is internal
            existing_dict.update(new_entries)
            new_dict = existing_dict

    # Serialize dict as pretty‑printed Python literal
    dict_literal = json.dumps(new_dict, indent=4, sort_keys=True)
    # Convert JSON syntax to Python (true/false/null)
    dict_literal = dict_literal.replace("true", "True").replace("false", "False").replace("null", "None")

    # Reconstruct file
    new_lines = lines[: start + 1] + [dict_literal + "\n"] + lines[end:]
    with open(TEMPLATE_PATH, "w") as f:
        f.writelines(new_lines)

    typer.echo(f"TASK_TEMPLATES {mode}d successfully.")
