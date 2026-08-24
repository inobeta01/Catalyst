

1. What we know

- The current STATUS.md tracks six fine‑grained steps (compose skeleton, trace‑shape contract, simulated workload, first failure‑mode, catalog expansion, eval harness).
- After moving to real agentic orchestration, the “trace‑shape contract” step is no longer required, and the trace-schema/ directory can be dropped.
- The author feels the document is cluttered with “too many issues” and wants a tighter, more actionable status view that reflects the new plan described in docs/designs/catalyst‑overview.md.

2. Design Goals

┌────────────────────────────────────────────────────────┬───────────────────────────────────────┐
│                          Goal                          │            Why it matters             │
├────────────────────────────────────────────────────────┼───────────────────────────────────────┤
│ Reduce noise – keep only the mile rows make the status page       │
│ drive work.                                            │ scannable and prevent “analysis       │
│                                  ysis”.                           │
├────────────────────────────────────────────────────────┼───────────────────────────────────────┤
│ Align with the new plan – the oventees that the status page       │
│ trace shape as a given (standard OTel spans) and       │ mirrors the current execution model.  │
│ removes the custom contract.                                      │
├────────────────────────────────────────────────────────┼───────────────────────────────────────┤
│ Signal blockers clearly – keep ths the author to see at a glance  │
│ arrows where a step truly depends on a prior one.      │ what must be finished before moving   │
│                                  rd.                              │
├────────────────────────────────────────────────────────┼───────────────────────────────────────┤
│ Maintain a single source of truthnts divergence between docs,     │
│ should be the go‑to place for anyone checking          │ README, and the actual repo.          │
│ progress.                                                         │
└────────────────────────────────────────────────────────┴───────────────────────────────────────┘

3. Proposed Revision Strategy

1. Delete the “Trace shape contract” step (now covered implicitly by the OTel conventions).
2. Merge related steps to keep the
   - Combine Step 1 (skeleton) and Step 3 (simulated agents) into “Foundational stack” – the core
     Docker‑compose + agents scaffo
   - Keep Step 4 (first failure mode) as the first concrete validation.
   - Keep Step 5 (catalog expansions the growth/automation lane.

3. Add a concise “Current focus” litionable step.
4. Remove the trace-schema/ directory reference from any “What exists today” block.

The revised markdown below implements those changes.

4. Rewritten STATUS.md (ready to copy‑paste)

# Catalyst — Status

> **One‑liner:** Catalyst is the realistic, repeatable test fixture for a Phoenix × AgentOps qualitative‑bridge plugin. Plugin ↔mory; they never see each other’sprocess.                                                                                           
**Last updated:** 2026‑08‑24                                                                       **Branch:** main
**Mode:** Builder (single user — plugin author)                                                    **Locked decisions:** Shared‑Phoenich B). Discrimination‑only v1.Corpus‑backed regression deferred to v2.                                                           
---                                                                                                
## Progress at a glance                                                                            
| Step | Description | Status |                                                                    |---|---|---|
| 1 | **Foundational stack** – Docker‑compose (LangGraph, Phoenix, AgentOps) + CLI stub (`catalyst run/reset/eval`) + initial LangGrap, brief‑writer) | 🟡 In progress |
| 2 | **First failure mode – prompt‑template drift** – validates the plugin against a real‑tool perturbation | 🟡 In progress |
| 3 | **Catalog expansion (+4 failure modes)** – build ≥5 seeded failure modes, each with
perturbed + control runs | ⬜ Block
| 4 | **Eval harness output** – `catalyst eval` runs the catalog, reads verdicts, and prints a
concise report | ⬜ Blocked by 3 |

*Legend:* ⬜ not started · 🟡 in pr · ❌ dropped

---

## Current focus

> **Next step:** Start the **Foundacompose.yml` on the floor, scaffoldthe CLI, and spin up the three LangGraph agents. No custom trace contract is needed; we rely on the
standard OpenTelemetry spans automaaph‑Phoenix integration.

---

## What exists today

/home/krugger00/Catalyst/
├── CLAUDE.md              (project‑level instructions)
├── docs/
│   └── designs/
│       └── catalyst‑overview.md   26‑08‑24)
└── .claude/               (empty; no trace‑schema directory needed now)

*Note:* The `trace-schema/` folder has been removed because real agentic orchestration uses the
standard OTel conventions automatic

---

## Step ledger (chronological log)

- **Step 1 – Foundational stack**
  - **Goal:** `docker compose up && catalyst eval` exercises LangGraph + Phoenix + AgentOps on a dev laptop with only LLM API keys and sandbox credentials.
  - **Definition of done:**
    - `docker‑compose.yml` brings uhoenix (shared memory), AgentOps(lifecycle UI).
    - `catalyst` CLI stub with `runnctional, not just placeholders).
    - `README.md` explains the one‑shot bring‑up flow.

- **Step 2 – First failure mode** (prompt‑template drift) – see
`catalyst/failure‑modes/prompt‑temp

- **Step 3 – Catalog expansion** – MLs (tool‑selection drift, retrystorms, hallucinated citations, premature termination).

- **Step 4 – Eval harness** – `catalyst eval` runs the full catalog, reads verdicts from Phoenix, and
prints a report in < 5 min.

---

## Success criteria (as restated in

- `docker compose up && catalyst evanual steps beyond LLM keys andsandbox credentials.
- ≥ 5 seeded failure modes each proL signal (perturbed vs. control).
- Plugin author can view the eval result (regressed modes, passing controls, infra errors) in < 5 min
from the terminal.
- Two fresh clones produce identical eval results for the same plugin version.
- Real‑tool traces conform to the sno bespoke contract needed).

---

### 5. Next Actions for the author

1. **Create `docker-compose.yml`** LangGraph, Phoenix, and AgentOpsimages.
2. **Add the CLI scaffold** (`catal`reset`, `eval` entry points).
3. **Implement the three starter agents** (triage, code‑review, brief‑writer) using the existing
prompt files under `workload/prompt
4. **Commit and run `docker compose up`** to verify that the stack boots without manual config.
5. Once the stack is stable, move t as the next focus.

---
