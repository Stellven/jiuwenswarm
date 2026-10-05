---
type: review
status: draft
tags: [review, draft, prd, m1]
---

# PRD review: architecture pushback

> **Superseded 2026-10-01** by the [full PRD review](prd-m1-full-review.md), which says which of these points the full PRD settles.
>
> **Draft, not yet sent.** Architecture's review of the PRD ("Product Requirements Document: AI4Research") and the PRD owner's kickoff messages. The PRD is the PRD owner's. This page only lists the points where it contradicts itself, asks for something the M1 runtime cannot do, or asks for something the design should not do. Each point names its evidence and what we ask for. Points that touch RSI, the Verifier or model routing name the owner to agree them with.

## The PRD contradicts itself

| # | Point | Evidence | We ask |
|---|---|---|---|
| 1 | **Three gate verdicts or five.** | PRD 4.3 and the Evaluator entry in section 3 name `PASS`, `FAIL`, `BLOCKED`. The kickoff's Verifier brief names `PASS`, `PASS_WITH_KNOWN_LIMITATIONS`, `FAIL`, `ENVIRONMENT_BLOCKED`, `ESCALATE_TO_HUMAN` | pick one. The design supports either: the three are the gate's decision, and the five can be derived from the same records ([design notes](capability-capsule-design-notes.md#gate-verdicts)). Owner: Verifier |
| 2 | **How many core capsules.** | PRD 4.1 lists six workflow capsules plus `verifier_capsule`. The kickoff says "6 core capsules (5 workflow + 1 verifier gate)" | confirm the list |
| 3 | **The `make_capsule.md` experiment cannot decide whether contracts exist.** | Section 3 sets CC's M1 state as testing "with and without `make_capsule.md` to determine if manual schemas are required". But 4.1 wraps every capsule in standardized schemas, 4.3's tier 1 reads the capsule contract, and the kickoff has RSI mutate against "static `make_capsule.md` schemas" | state the experiment as a measurement of what per-capsule contracts add to output quality. The Verifier and RSI depend on contracts either way |
| 4 | **Two different nodes produce the Research Brief.** | Requirement Compilation is "an agentic prompt parser". Intention Compilers Phase 1 is "template-based mapping" into "static variables" | say which one produces the Brief in Phase 1, and what the other one does |

## The M1 runtime cannot do this yet

The M1 stack routes every model call through the Codex subscription runtime. What it cannot do is recorded in the design, read from the code ([B1](../archive/b1-design.md), [permissions](../capsule/permissions.md#gaps-and-conflicts)).

| # | Point | Evidence | We ask |
|---|---|---|---|
| 5 | **Token budget ceilings in tier 1** (4.3, and "telemetry: token consumption against budget") | the Codex service reports no token usage ([B1](../archive/b1-design.md), Model usage) | M1 budgets time only, or Model Routing makes the adapter report tokens. Owner: Model Routing |
| 6 | **Halting to `human_session`** (section 3 Evaluation, 4.3) | `human_session` needs a backend with sessions. Only the team backend has one, and this runtime does not start it. The Codex adapter also refuses a reply ([B1](../archive/b1-design.md), Stopping) | M1 halts and shows the failure. A reply path is planned as its own work item. Owner: Verifier, with Model Routing |
| 7 | **Operator calls mediated by jiuwenswarm's permission system** (4.4; Operators; Account Management) | the subscription runtime accepts text only and rejects every tool request, so the permission rail never runs ([permissions](../capsule/permissions.md#gaps-and-conflicts)) | accept that on this runtime the CC runner and `op.workspace_io` enforce operator whitelists and workspace bounds |
| 8 | **Code that must run:** POC scripts "in an isolated workspace", "basic runtime metrics" for benchmarking | the runtime executes no tools (point 7). Builder Phase 1 is "static artifact generation" of text and Markdown, which does not run code | name where POC and benchmark code run: the workspace through a code capsule, or a Code Mode worktree |
| 9 | **Operators on the subscription** ("routing application requests through the active subscription to bypass API access limitations") | *to confirm before sending:* DeepSearch and CodeSearch appear to need their own LLM and search API keys | if confirmed, name who provides the keys. Owner: Model Routing |

## The design should not do this

| # | Point | Evidence | We ask |
|---|---|---|---|
| 10 | **The LLM judge emits the verdict** ("returns a structured JSON verdict", 4.3) | nothing judges itself, and judges are not calibrated yet. So the judge writes an assessment, and deterministic gate code emits the verdict ([trust](../capsule/trust.md#block-for-safety-label-for-quality), [policy gates](../schemas/policy.md#gates)) | the Verifier agrees that tier 2 assesses and the gate decides. Owner: Verifier |
| 11 | **Screening as a "Deterministic Rubric Gate"** (section 3) | model rubric scoring is not deterministic. Screening is a stage capsule, `screening_capsule`, and gates are the Evaluator's | call it a rubric-scored screening stage, checked by the Evaluator Gate like every stage |
| 12 | **A capsule as one `.md` file** (4.1: `requirement_capsule.md`, ...) | a capsule is a contract plus its code or skill files and its tests ([capsule](../capsule/capsule.md)) | name capsules, not files, so `make_capsule.md` is read as the contract, not the capsule |
| 13 | **"Fully autonomous capsule generation and registry management"** (CC future state) | the referee never evolves: admission, the tests and the policy stay out of any autonomous loop, and new capsules enter only through admission ([RSI](../capsule/rsi.md#what-must-never-evolve)) | keep the future state, bounded as "autonomous generation, through admission". Owner: RSI |
