# Design: Catalyst — fixture for a Phoenix × AgentOps qualitative-bridge plugin

Revised 2026-08-24
Branch: main
Repo: krugger00/Catalyst
Status: DRAFT
Mode: Builder
Supersedes: catalyst-overview.md (2026-08-20) — real-agent revision

## Problem Statement

Catalyst is the realistic, repeatable test fixture for a separate qualitative-bridge plugin. The plugin reads spans from Phoenix, applies qualitative judgments (tone, prompt drift, hallucination patterns, behavioral regressions), and persists verdicts back into the same Phoenix trace as annotations. Catalyst emits traces on demand; the plugin (somewhere) observes Phoenix; Catalyst reads verdicts back from Phoenix and asserts against expected signals.

**Revision note:** the workload is no longer fully synthetic. Agents perform real tool execution (sandboxed) against real-world data (redacted), rather than scripted responses against fabricated fixtures. This closes the "is this shaped like production" gap the original design deferred — at the cost of introducing new problems (sensitive data, nondeterminism, sandboxing) the synthetic version was explicitly designed to avoid.

Two gaps in current agent observability stacks still motivate the plugin:

- **Phoenix gap** — weak LLM-as-judge story in the version under use; trace collection is strong, qualitative grading is not.
- **AgentOps gap** — weak qualitative assessment (tone, prompt drift, hallucination patterns, behavioral regressions); lifecycle/cost/observability capture is strong, qualitative judgment is not.

The plugin lives in the seam between them. Catalyst is the proof that the plugin discriminates and remains stable over time — now under real operating conditions, not just controlled ones.

## What Makes This Cool

The "whoa" factor is **closing the loop with discrimination as the test surface**, against real agentic behavior rather than a simulation of it. Every plugin change runs against a curated failure-mode catalog — declared perturbations on a workload doing genuine multi-step tool use over real-world data — and the plugin gets graded on whether it catches what it should and doesn't false-positive on what it shouldn't, including false-positiving on ordinary real-world noise (a flaky API retry, not an injected one). The grading happens through shared Phoenix memory; the plugin and Catalyst never touch each other.

## Constraints

- Audience is the plugin author — single user. OSS distribution is deferred-but-designed, not built.
- Catalyst and the plugin **share Phoenix as memory**. No subprocess invocation, no vendored dep, no installed package, no sidecar store. The plugin is wherever Phoenix can reach it; Catalyst never sees the plugin's process.
- **Real tool execution is sandboxed, never direct.** Agents under a perturbation are, by design, being made to misbehave (retry storms, tool misroute, etc.). A misbehaving agent with unrestricted real tool/API access is a live-incident risk, not just a test-fixture risk. All real tool calls route through a sandboxed runtime and ephemeral/test credentials — never production accounts.
- **Real-world data is redacted before it is committed.** Unlike the original design, Catalyst's inputs are no longer synthetic by construction, so Catalyst now owns a redaction step it previously assumed was the plugin's problem. Raw real-world data is never committed to the repo; only sanitized fixtures are.
- **Determinism is handled by record/replay, not by avoiding real systems.** Control runs replay a captured real interaction; a separate live/exploratory mode may hit real tools when fresh variance is deliberately wanted. This is what keeps perturbed-vs-control comparisons meaningful once real tools are in play.

## Premises

1. The plugin — not Catalyst — is the close-the-loop engine. Catalyst is the fixture.
2. Catalyst and the plugin share Phoenix as memory. No direct connection, no shared process, no vendored coupling.
3. Single-user scope. OSS-ready is a future-friendly property, not a v1 requirement.
4. Compose existing pieces (LangGraph, Phoenix, AgentOps, a sandboxed tool runtime) rather than re-implementing them.
5. **The workload now performs real agentic orchestration**: real tool calls (sandboxed) over real-world data (redacted), rather than a synthetic stand-in whose trace shape merely resembles production. This removes the original premise that the workload is "allowed to be artificial."
6. **Corpus-backed regression moves into v1.** The original design deferred this to v2 as "designed-but-dormant"; using real-world data makes it immediately relevant, since real inputs carry real historical variance that a synthetic catalog can't.
7. Phoenix + AgentOps are the canonical primitives; Catalyst + the plugin fill the qualitative gap *between* them, not by replacing either.

## Verdicts & Failure-Mode Contract (working draft)

Unchanged in shape from the original design — the plugin writes its verdict to Phoenix as a structured annotation on each trace, Catalyst reads the same annotation back:

```
verdict = {
  "mode": "pass" | "fail" | "warn",
  "checks": [{ "name": "...", "passed": bool, "evidence": "..." }],
  "qualitative": { "summary": "...", "scores": {...} }
}
```

**New requirement:** with real tools in play, the contract must distinguish a genuine perturbation-caused failure from real-world noise (an actual flaky API call, a real transient tool error). The first failure mode built under this revision should explicitly validate that noise doesn't get misread as a plugin failure.

```yaml
# catalyst/failure-modes/prompt-template-drift.yaml
id: prompt-template-drift
description: A prompt template segment is swapped, simulating silent prompt-version drift.
trigger:
  agent: brief-writer
  perturbation: replace_prompt_segment
  args:
    segment_id: closing-cta
    replacement_text: "Buy now."
workload_inputs: fixtures/brief-writer/standard.json   # redacted, real-world-derived
control_inputs: fixtures/brief-writer/standard.json    # no perturbation, replayed real tool responses
expected:
  perturbed_run: { verdict_mode: fail, must_match_check: "prompt_drift_detected" }
  control_run:   { verdict_mode: pass, must_not_match_check: "prompt_drift_detected" }
realism_bar: prompt-version drift is the canonical regression mode (observed in incident logs)
```

## Approaches Considered

### Approach A — Subprocess CLI
Ruled out — couples Catalyst and the plugin through process invocation, forces version-pinning between independently-versioned codebases.

### Approach B — Shared Phoenix Memory (adopted)
Plugin and Catalyst communicate only through Phoenix. No direct connection. Recommended and locked, pending Phoenix's annotation API validated for structured round-trip (Stage 2).

### Approach C — Sidecar Verdicts File
Ruled out — adds a third state location alongside Phoenix and AgentOps.

## Recommended Approach

**B**, unchanged. What's new is what feeds it: real tool execution and real-world data, rather than a fully synthetic workload. The shared-memory principle still holds regardless of whether the traces underneath are synthetic or real — that was the point of decoupling Catalyst from the plugin in the first place.

## Open Questions

- **Industry-standard trace shape specifics** — unchanged from original, resolved before Stage 3.
- **Verdict annotation shape in Phoenix** — unchanged from original, resolved in Stage 2.
- **Sandboxing mechanism for real tool execution** — E2B, local Docker sandbox, or a proxy layer with ephemeral credentials. Needs to be decided before any real-world workload runs, since perturbed agents will deliberately misbehave.
- **Redaction pipeline tooling** — e.g. Presidio or equivalent, plus a human review gate before a sanitized fixture is committed. Decided before Stage 3 begins (now effectively a new Stage 0.5).
- **What "reproducible" means now** — no longer byte-identical trace equality across clones (real tool calls introduce network/API variance). Needs a redefinition: verdict-stability across N runs of the same recorded/replayed interaction.
- **Noise vs. failure classification** — how the eval harness distinguishes a plugin correctly flagging a perturbation from a plugin incorrectly flagging ordinary real-tool jitter.

## Success Criteria

- `docker compose up && catalyst eval` exercises the full stack (LangGraph + Phoenix + AgentOps + sandboxed tool runtime) on a developer laptop with no manual configuration beyond setting LLM API keys and sandbox/test credentials.
- The discrimination suite has ≥5 seeded failure modes at v1, each with a perturbed run and a control run (control run replayed from captured real interactions for determinism), each producing a stable PASS/FAIL signal by reading the plugin's verdict annotation back from Phoenix.
- A plugin author changing the qualitative judgment logic can see the eval result (which failure modes regressed, which controls passed, which infra-errored, which were noise) in under 5 minutes without leaving the terminal.
- The fixture is **verdict-stable**, not byte-identical: two fresh clones running the same recorded/replayed interaction produce the same verdict for the same plugin version; live/exploratory runs against real tools are understood to vary and are excluded from this guarantee.
- No raw, unredacted real-world data ever reaches the committed repo. Only sanitized fixtures do.
- The real-tool-executing workload's traces conform to the same industry-standard shape as the plugin observes in production — no longer an assumption, but a fact by construction, since the workload now does the real thing.

## Distribution Plan

Single-user scope means no public distribution in v1. Distribution surface is the git repo + the docker-compose + sandbox/credential setup docs. Future OSS-readiness: the docker-compose + CLI should be the whole story for a new developer, though real-tool execution means "no manual setup" now also needs to cover getting safe test credentials and a sandbox runtime configured — this is a heavier bar than the original synthetic-only design implied.

## Execution Plan — Stages

## Stage 0 — Environment & repo bootstrap

(unchanged)

Tech: docker-compose.yml — langgraph-runtime, phoenix, agentops. CLI scaffold via click/typer, catalyst run/reset/eval installed with pip install -e ..
Exit criteria: docker compose up && catalyst reset works with no manual steps beyond .env keys.

## Stage 1 — Agent creation (moved first)

**Goal**: Get three working LangGraph agents doing genuine multi-step reasoning, before anything else is locked.

**Tech**: LangGraph StateGraph per agent (triage, code-review, brief-writer), langchain model wrappers for your LLM provider, OpenInference auto-instrumentation wired in from the start so spans emit immediately — you want real trace data to look at in Stage 2, not a hypothetical schema.
**Tool interfaces, stubbed for now**: define the real tool interfaces (file ops, code exec, retrieval, whatever each agent needs) as typed function signatures, but back them with mocked/canned responses at this stage — not sandboxed real execution yet. This lets you iterate on agent logic and prompts fast without Stage 3's sandbox/credential plumbing being a dependency.
**Prompts**: one prompt file per agent under workload/prompts/, versioned from day one (this matters later for the prompt-drift failure mode).
**Owner note**: because tool calls are stubbed here, don't treat any trace produced in this stage as schema-final — Stage 2 may require rework once real tool calls (Stage 3) replace the stubs and produce different span shapes (real gen_ai.tool.* attributes vs. mocked ones).
**Exit criteria**: all three agents run end-to-end locally, produce a visible trace in Phoenix's UI, and behave sensibly on one fixture input each (even if that fixture is still a placeholder, not yet real-world-derived).

## Stage 2 — Trace shape contract

**Goal**: Lock the schema against real emitted spans, not a hypothetical one.

**Tech**: OpenInference semantic conventions as source of truth (check against the Phoenix version pinned in Stage 0's compose — annotation/trace conventions have shifted across releases). Cross-check against OTel GenAI conventions where they diverge (span kind naming, tool-call attributes).
**Advantage of the reorder**: you're documenting trace-schema/span-contract.md by inspecting Stage 1's actual output, which is more concrete than designing it from scratch — but flag any span shape that will change once Stage 3 replaces stubbed tools with real ones, so the contract accounts for both.
**Exit criteria**: trace-schema/span-contract.md reviewed and frozen; explicitly annotated where stubbed-vs-real tool calls are expected to differ.

## Stage 3 — Sandbox & redaction pipeline (was Stage 0.5, now here)

**Goal**: Replace Stage 1's stubs with real, safely-executed tools over real, safely-redacted data.

**Sandbox tech**: E2B or local Docker sandbox for code execution; a credential-proxy layer with ephemeral/test-scoped keys for real external APIs. Wire this into the tool interfaces already defined in Stage 1 — you're swapping the implementation behind an existing interface, not redesigning the agents.
**Redaction tech**: presidio (or equivalent) pass over raw real-world data, plus a human review gate before anything is committed. Pipeline: corpus/raw/ (gitignored) → redaction/pipeline.py → corpus/sanitized/ (committed).
**Determinism**: record real tool responses on first capture into workload/replay_cache/; control runs replay from there going forward.
**Exit criteria**: each agent's stubbed tool calls are replaced with sandboxed real ones; a raw real-world sample passes through redaction with no PII in the sanitized output; a captured interaction replays deterministically.

## Stage 4 — Verdict annotation transport

(unchanged from before, now Stage 4)

**Tech**: Phoenix's span annotation API (log_annotations or REST, version-dependent). Throwaway script to write/read back a full verdict object matching the contract shape.
**Also resolve**: the poll/timeout contract in phoenix_client.py — how catalyst eval waits for the externally-running plugin without false timeouts.
**Exit criteria**: round-trip script proves the verdict contract survives Phoenix, poll/timeout behavior documented.

## Stage 5 — First failure mode, end to end

**Tech**: prompt-template-drift.yaml, perturbations/replace_prompt_segment.py.
**New validation** (from real tools/data): confirm the plugin doesn't false-positive on genuine real-tool jitter — this is where noise-tolerance.yaml earns its place in the catalog.
**Exit criteria**: correct PASS/FAIL on perturbed and control runs, plugin genuinely running as a separate process, no noise misclassified as failure.

**Sequencing note**: Stage 1 no longer blocks on Stage 2 or 3 — that's the whole point of the reorder. But Stage 3 does block Stage 5's end-to-end assertion, same as before: you can't validate the plugin against real tool execution until the sandbox exists. The one new risk worth tracking explicitly: if Stage 2's schema-lock reveals that stubbed and real tool calls produce meaningfully different span shapes, some of Stage 1's agent code may need adjustment once Stage 3 wires in the real tools — budget for that possibility rather than treating Stage 1 as fully final.