# Catalyst

Synthetic software agency workload for tracing and evaluating LLM agents with Phoenix, LangGraph, and AgentOps.

## Structure

- `cli/` — Catalyst CLI entrypoint (`run`, `reset`, `eval`)
- `workload/` — Synthetic "small-scale software agency" with triage, code-review, and brief-writer agents
- `failure-modes/` — Catalog of failure-mode YAML files (one per perturbation)
- `perturbations/` — Code triggered by each failure-mode YAML
- `trace-schema/` — Trace contract and OpenTelemetry conventions
- `tests/` — Unit and integration tests

## Quick Start

```bash
cp .env.example .env
export $(cat .env | xargs)
docker compose up
```

## Note on the qualitative-bridge plugin

The qualitative-bridge plugin lives in a separate repository maintained by its author. It only touches Phoenix.
