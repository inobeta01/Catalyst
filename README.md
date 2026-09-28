# Catalyst

**Synthetic software agency workload** that orchestrates LLM agents using **Phoenix**, **LangGraph**, and **AgentOps**.  The project provides a self‑contained Docker environment that spins up the full stack and runs a configurable catalog of failure‑mode perturbations.

---

## Architecture Overview

```
+----------------+      +------------+      +------------+
|   Catalyst CLI | ---> |  Docker‑   | ---> |  Phoenix   |
| (run, reset,   |      |  compose   |      |  (tracing) |
|  eval)          |      +------------+      +------------+
+----------------+            |                     |
                               |                     |
                               v                     v
                     +----------------+    +----------------+
                     |   LangGraph    |    |   AgentOps     |
                     | (workflow      |    | (agent UI)      |
                     | orchestration) |    +----------------+
                     +----------------+
```

* **Catalyst CLI** – entry point (`catalyst run`, `catalyst reset`, `catalyst eval`).
* **Docker‑compose** – brings up three services:
  * **Phoenix** – OpenTelemetry‑enabled tracing backend.
  * **LangGraph** – executes the agentic workflow defined under `workload/`.
  * **AgentOps** – UI for inspecting agent lifecycles and results.
* **Workload** – contains three baseline agents (triage, code‑review, brief‑writer) plus a catalog of failure‑mode YAML files that perturb the agents.
* **Failure‑modes & Perturbations** – each YAML describes a perturbation; corresponding code under `perturbations/` implements the change.
* **Trace‑schema** – defines the OpenTelemetry contract used by Phoenix (can be removed once standard OTel spans are sufficient).

---

## Quick Install & Setup

```bash
# 1️⃣ Clone the repo (if you haven't already)
git clone https://github.com/your-org/catalyst.git && cd catalyst

# 2️⃣ Install environment variables
cp .env.example .env
# Export them for the current shell session
export $(cat .env | xargs)

# 3️⃣ Set up your environment

Copy `.env.example` to `.env` and update `DATABASE_URL` with your Neon connection string:

```bash
cp .env.example .env
```

Edit `.env` and set:

```
DATABASE_URL="postgresql://username:password@ep-xxxx-pooler.region.aws.neon.tech/neondb?sslmode=require"
```

# 4️⃣ Build and start the stack (Phoenix, AgentOps, LangGraph)
docker compose up --build -d

# 5️⃣ Verify services are healthy (optional)
#    Phoenix  : http://localhost:6006
#    LangGraph : http://localhost:8000
#    AgentOps  : http://localhost:8000
```
```

The stack will launch:
* Phoenix listening on the default OTLP port.
* LangGraph serving the workflow API.
* AgentOps UI accessible via a browser.

---

## Command Reference

### `catalyst run`
Run a task using its description from the built‑in templates. No external fixture file is required.

```bash
catalyst run --task-id <TASK_ID> --run-id <ID>
```

- `--task-id` (required): One of the IDs defined in `workload/prompts/templates.py` (e.g., `task-101`).
- `--run-id` (required): Unique identifier for this run (e.g., a UUID or timestamp).

The command automatically builds the fixture from the task description and invokes the orchestration graph.

### `catalyst reset`
Reset all Catalyst state (clears Phoenix traces, AgentOps sessions, cached fixtures).

```bash
catalyst reset
```

### `catalyst eval`
Execute a single task with optional random failure injection.

```bash
catalyst eval --task-id <TASK_ID> --run-id <ID>
```

- `--task-id` (required): Task identifier from the templates.
- `--run-id` (required): Unique identifier for this evaluation run.

The command loads the task description, randomly enables its failure mode (≈ 50 % chance), runs the orchestration, and logs a verdict.

### `catalyst feed`
Manipulate the task catalog.

```bash
catalyst feed --mode rewrite --source new_tasks.json   # replace all tasks
catalyst feed --mode append  --source extra_tasks.json  # add new tasks
catalyst feed --mode clear                          # empty the catalog
```

`new_tasks.json` and `extra_tasks.json` should contain a JSON object mapping task IDs to their definitions.


---

## Extending the Catalog

Add a new failure‑mode by creating a YAML file in `failure-modes/` and the corresponding implementation under `perturbations/`.  The CLI automatically discovers new entries, so no additional configuration is required.

---

## Note on the Qualitative‑Bridge Plugin

The qualitative‑bridge plugin lives in a separate repository and only interacts with **Phoenix**.  It is not required for the core Catalyst workflow.

---

## License

[Apache 2.0](LICENSE)
