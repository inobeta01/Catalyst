# Agent Evaluation Matrix — Industry Standards vs. AgentOps Coverage vs. Our Build

**Purpose:** Map the dimensions a reputation/evaluation score should cover, grounded in existing industry standards and benchmarks (SWE-bench, Tau-bench, GAIA, OSWorld, OWASP LLM Top 10, and current agent-observability practice) — and identify exactly what AgentOps (our chosen open-source base) already handles, what we need to build ourselves, and what's still genuinely unsettled across the whole industry, not just for us.

**Status key:**
- ✅ **AgentOps covers this today** — don't rebuild it, integrate/consume it.
- 🔧 **We build this** — confirmed gap in existing open-source tooling, ours to own.
- ⚠️ **Industry-wide, still emerging** — actively being worked on by researchers/multiple companies, not a solved or standardized problem anywhere yet. Build a basic version if in scope, but don't over-promise rigor here.
- 🚫 **Deliberately out of v1 scope** — real, but excluded on purpose per earlier design decisions.

---

## 1. Operational monitoring (the "did it run, how much did it cost" layer)

| Dimension | Industry reference point | Status | Notes |
|---|---|---|---|
| Latency per call/session | Standard APM practice | ✅ AgentOps covers | Tracked out of the box |
| Cost / token spend tracking | Standard LLMOps practice | ✅ AgentOps covers | Granular cost tracking, spend visualization, per-agent |
| Tool usage statistics | Standard AgentOps practice | ✅ AgentOps covers | Detailed analytics on which tools get called and how often |
| Failure/error/crash detection | Standard AgentOps practice | ✅ AgentOps covers | Includes recursive-loop (infinite loop) detection |
| Multi-agent interaction tracking | Standard AgentOps practice | ✅ AgentOps covers | Native support for multi-agent sessions |
| Session replay / step-by-step trace | Standard AgentOps practice | ✅ AgentOps covers | Replay analytics, time-travel debugging |
| Session-wide summary statistics | Standard AgentOps practice | ✅ AgentOps covers | Session ID, duration, token totals, etc. |

**Takeaway:** this entire layer is solved. Consume AgentOps (or Langfuse) directly — building any of this ourselves would be pure duplication.

---

## 2. Security & compliance layer

| Dimension | Industry reference point | Status | Notes |
|---|---|---|---|
| Audit logs for compliance (SOC 2 / HIPAA / NIST AI RMF) | Enterprise compliance standards | ✅ AgentOps covers | Paid-tier feature, already built |
| PII leak detection | Standard data-security practice | ✅ AgentOps covers | Listed explicitly under compliance & security |
| Profanity / basic content flagging | Standard content-moderation practice | ✅ AgentOps covers | Same feature set as above |
| Prompt injection **detection** | OWASP LLM Top 10 (LLM01) | ✅ AgentOps covers | Detects known injection/secret-leak patterns |
| Adversarial **robustness benchmarking** (does the agent actually resist injection under sustained attack, scored) | OWASP LLM Top 10 threat taxonomy + emerging benchmarks (Agent Security Bench, OpenAgentSafety) | ⚠️ Industry-wide, still emerging | Detection ≠ benchmarking. No one has a mature, gameproof scoring methodology yet — the benchmark itself can be attacked by a capable agent. Treat as a real gap, not an easy build. |

**Takeaway:** basic detection is solved and available to us for free. Turning "we detected an injection attempt" into "here's a reliable robustness *score*" is a known, hard, currently-unsolved problem industry-wide — not something to promise a clean version of in v1.

---

## 3. Correctness evaluation layer (the part nobody's shipped cleanly)

| Dimension | Industry reference point | Status | Notes |
|---|---|---|---|
| Basic custom test execution against an agent | AgentOps "Custom Tests" feature | ✅ AgentOps covers (shallow) | Runs domain-specific tests, but not a structured contract framework |
| Public benchmark leaderboard comparison | AgentOps "Public Model Testing" feature | ✅ AgentOps covers | Tests agents against known public benchmarks/leaderboards |
| Deterministic state-contract verification (did the real downstream system reach the expected state) | SWE-bench Verified, Tau-Bench methodology (execution-based verification) | 🔧 We build | This is our core differentiator — checking real state change, not just "did a test run" |
| Schema/shape validation of tool responses | Standard software testing practice, adapted to agents | 🔧 We build | Not a distinct AgentOps feature; needs contract definitions per tool |
| Business invariant / rule violation checks | Property-based testing practice (Hypothesis/QuickCheck lineage) | 🔧 We build | Task-agnostic rules (e.g. "balance never negative") — no existing agent tool does this natively |
| Subjective output grading via rubric (LLM-as-judge) | DeepEval, Confident AI, MLflow LLM-as-Judge practice | ✅ Partially covered elsewhere (not AgentOps-native) | AgentOps lists basic "Evals"; deeper rubric-based judging is better sourced from DeepEval/MLflow patterns than reinvented |
| Contract registry (org-authored, per-tool judging rules) | No direct precedent — adapted from API contract-testing practice (e.g. Pact) | 🔧 We build | Nobody in the agent-observability space ships this specifically for MCP tools yet |

**Takeaway:** this is genuinely our lane. Operational monitoring and basic detection are commodity; turning a trace into a *verified correctness judgment* against a real contract is the confirmed, still-open gap.

---

## 4. Advanced / aggregate scoring layer

| Dimension | Industry reference point | Status | Notes |
|---|---|---|---|
| Single pass/fail score per task | Most current benchmarks (SWE-bench, GAIA, OSWorld) | ✅ Well-established methodology | Easy to adopt as a baseline, not novel |
| Confidence intervals across repeated runs (accounting for flakiness) | Named explicitly as missing by current benchmark critiques | 🔧 We build | Confirmed unsolved: most leaderboards report a single number, not a variance band |
| Cost-aware scoring (pass-rate vs. dollars-per-task, Pareto frontier) | Named explicitly as an active, unstandardized research area | ⚠️ Industry-wide, still emerging | A few academic groups/companies are actively working on this; no shipped open-source standard yet. Good target — but expect the methodology itself to still be moving under you. |
| Drift detection (a previously-passing contract degrading over time) | Adapted from standard software regression-testing practice | 🔧 We build | Not a feature of AgentOps or the correctness-eval tools surveyed |
| Cross-organization portable reputation score | ERC-8004 (crypto-native), ReputAgent (early-stage startup) | 🚫 Deliberately out of v1 scope | Real attempts exist but are documented as not yet meeting the conditions for a trustworthy signal — correctly excluded from our scope per earlier design decisions |

---

## Summary: where to actually spend effort

| Layer | Build it ourselves? |
|---|---|
| Operational monitoring (latency, cost, tool stats, replay) | No — consume AgentOps directly |
| Basic security detection (PII, injection detection, audit logs) | No — consume AgentOps directly |
| Adversarial robustness *scoring* | Not yet — track industry progress, don't attempt a v1 version |
| Deterministic contract-based correctness | **Yes — this is the core product** |
| Confidence-interval + cost-aware aggregate scoring | **Yes — confirmed open gap, buildable** |
| Cross-org reputation | No — explicitly deferred |
