# Canonical vocabulary and PRD crosswalk

`Tier 3 · Part of: [Reference](reference/README.md)`

This Git-tracked page is the shared naming register and PRD-to-architecture crosswalk for maintained terms, prose and diagrams. The design package is authoritative. Any team member can propose edits; affected owners check meaning and use. Use canonical terms in design, tasks, specifications and agent instructions. Stable machine identifiers remain in their contract and task registries. The received PRD remains verbatim; its words and clause numbers remain source references. The crosswalk explains responsibilities and relationships rather than declaring unlike components interchangeable. The [decisions](method/decisions.md#decisions-and-source-amendments) retain actual amendments; vocabulary edits do not change product scope. Definitions and examples still matter; matching labels alone do not ensure shared understanding.

## Canonical terms

Each term has one meaning and one home page. Use the term exactly. The phrases in the last column are **forbidden** in maintained pages, because they suggest a second meaning. `validate.py` reads this table and fails on any forbidden phrase outside `diagrams/`, this page, [decisions](method/decisions.md) and [owner rulings](side-systems/owner-rulings.md). Matching ignores case. Each forbidden phrase is written in backticks.

| Term | Meaning | Home | Forbidden |
|---|---|---|---|
| server host | The one machine that runs M1: the GB10 GPU host. Users never run M1 on their own computers | [Platform](platform/README.md) | `workstation`, `local machine`, `local execution host` |
| private network access | Users reach the app from the LAN or VPN at the server's private address, with a session token in every request ([D35](method/decisions.md#d35)) | [Platform](platform/README.md) | `loopback`, `127.0.0.1:5173` |
| app container | The container that holds the whole product: web UI, control API, runtime, model bridge, confined executor, state | [Platform](platform/README.md) | `workflow application image` |
| sidecar container | The one container that holds the platform benchmark runner and the test runner. Both are ordinary authenticated clients of the control API ([D36](method/decisions.md#d36)) | [Sidecar](development-tools/sidecar/README.md) | `benchmarker`, `benchmark container`, `development sidecar` |
| platform benchmark runner | Scores whole product runs from outside, inside the sidecar container. Not the Research Benchmark CC | [Benchmark runner](side-systems/benchmark-runner.md) | `platform benchmarker` |
| RSI workbench | The human-run RSI system in its own container. Built in M1, off the hot path | [RSI workbench](side-systems/rsi-workbench.md) | `offline RSI`, `optional RSI` |
| hot path | Code a research run cannot work without | [1. System](1-system.md) | |
| off the hot path | Built in M1, but a run works when it is absent, off or broken | [1. System](1-system.md) | `optional to the core`, `optional integration`, `later/optional` |
| later work | Not in M1. Named in [D21](method/decisions.md#d21) or a later milestone | [Decisions](method/decisions.md) | |
| Codex fallback | The fixed Codex route, chosen before a model call when the router is enabled but fails, times out, names an unapproved model, halts or replies with no route. The only meaning of "fallback". When the router is off or not installed, the Codex route is simply the default and is not a fallback | [Routing contract](reference/model-routing-contract.md) | `fallback mode`, `static fallback`, `fallback template`, `fallback workflow`, `automatic fallback`, `silent fallback` |
| router alternate model | The router's own spare model, chosen inside the router before the call | [Routing contract](reference/model-routing-contract.md) | `fallback_model_id`, `fallback model` |
| plan source | The run setting `plan_source`: `static` (the static template) or `planned` (the Planner node). Chosen before the run, on the run request ([D39](method/decisions.md#d39)). The only plan-source switch | [Run plan](reference/run-plan.md) | `plan_mode`, `static mode`, `planned mode`, `run mode` |
| static template | The hand-written plan used when `plan_source` is `static`. The PRD's Phase 1 Default DAG together with the Intention Compiler | [Run plan](reference/run-plan.md) | |
| checking profile | The pinned record that says which checks and verifier criteria are mandatory for one CC version. Owned by the verifier owner. At the static plan gate, which has no verifier, the check plan's `profile_ref` names the static template ([run plan](reference/run-plan.md)). The only profile name for this idea | [Verifier CC page](reference/capsules/verifier.md#checking_profile-contract) | `gate profile`, `guard profile`, `guard_profile_ref`, `check profile` |
| node finalization profile | A separate record, owned by protected configuration. It is not a form of the checking profile. The node gate reads it ([checking records](reference/checking.md#node-finalization-profile)) | [Checking records](reference/checking.md#node-finalization-profile) | |
| check bundle | The pinned deterministic checks of one CC version (PRD Tier 1). "Guard" is retired as a component name: say check bundle, verifier CC, gate decision or checking | [Checking](checking/README.md) | `guard architecture`, `guard resolver`, `mutation guard` |
| verifier CC | The general CC that assesses one output against its CC's declaration (PRD Tier 2). Gives an assessment, never a decision | [Verifier](reference/capsules/verifier.md) | `plan verifier`, `verifier agent` |
| gate decision | The protected record that advances or halts one output, or a whole node (node gate decision) | [Checking](reference/checking.md) | |
| work subnode | One work CC call plus its check bundle | [Node execution](reference/node-execution.md) | `execution subnode` |
| verifier subnode | One verifier CC call on one output, created by the scheduler at dispatch | [Node execution](reference/node-execution.md) | |
| `cc.router.enabled` | The one switch for the API router. Its mirrors are listed in the [routing contract](reference/model-routing-contract.md#routerport-the-hot-path-seam) | [Routing contract](reference/model-routing-contract.md) | `routing_mode` |
| `evolution.rsi` `propose` | RSI may submit a child; admission stores it inactive ([declaration](reference/declaration.md)). `submit` is rejected in M1 ([D34](method/decisions.md#d34)) | [Declaration](reference/declaration.md) | |
| `may_change` | `evolution.may_change`: the only parts of a CC an RSI child may change. Missing or empty means nothing ([D34](method/decisions.md#d34)) | [Declaration](reference/declaration.md) | `evolution.frozen` |
| PRD core M1 gate | Phase 1, Stages 0–7 and their required end-to-end run, verification, benchmark evidence and completion report ([D40](method/decisions.md#d40)) | [Delivery phases](method/phases.md) | `core acceptance` |
| interaction mode | The submission field `interaction_mode`: `interactive` (a person is present) or `headless`. The run configuration freezes it and the gate host branches on it ([D48](method/decisions.md#d48)) | [Client submission](reference/field-catalog.md#client-submission) | |
| host launcher | Compose up and down on the server host. It owns container lifecycle and runs the cases that kill the router process or stop a container. The test runner cannot do either | [Sidecar](development-tools/sidecar/README.md) | |
| selector | A rule in a static template that stands for every Brief item of one kind. The binder expands it against the accepted Brief ([D47](method/decisions.md#d47)) | [Run plan](reference/run-plan.md#selectors) | |
| partial | The run outcome when some node failed and independent branches still finished. Accepted artifacts and all evidence are kept ([D49](method/decisions.md#d49)) | [Run plan](reference/run-plan.md) | |
| skipped | The state of a node that did not run because a dependency failed. The failed node is named as the reason ([D49](method/decisions.md#d49)) | [Run plan](reference/run-plan.md) | |

## Identities and outcomes

Use role-qualified names: "verifier CC on `intent_ir`", "RSI referee", "fixture oracle", "protected gate host".

| Term | Rule |
|---|---|
| Declaration name / version / hash | Stable capability name, display version and exact immutable identity are distinct. Never use a display label as a content pin. |
| Product account / execution identity | The product user and durable profile are independent of OS identity and workspace. The session token authorizes control API requests. The confined executor runs under its own OS identity. |
| Artifact type / port / reference | Type names meaning, port names the input or output role, reference identifies stored content. A path alone does not prove accepted identity or freshness. |
| Freeze / protocol registration | Graph freeze fixes topology and bindings before research execution. Hypothesis registration later fixes experimental criteria before build or measurement. |
| NOT_RUN / unavailable / stale | No observation, unavailable telemetry, or invalidated evidence. None means zero cost, failed science, or a pass. |

## PRD artifact names

PRD artifact names map to lowercase internal names ([D23](method/decisions.md#d23)). Enum values keep their schema spelling.

| PRD name | Internal name |
|---|---|
| `Research_Brief.json` | `research_brief.json` |
| `Hypothesis_Blueprint.json` | `hypothesis_blueprint.json` |
| `Candidate_Set.json` | `candidate_set.json` |
| `Opportunity_Card.json` | `opportunity_card.json` |
| `POC_Artifact_Bundle.zip` | `poc_artifact_bundle.zip` |
| `Benchmark_Payload.json` | `benchmark_payload.json` |
| `Evaluation_Verdict.json` | `evaluation_verdict.json` |
| `Phase_1_Completion_Report.md (also 2 and 3)` | `phase_1_completion_report.md` |
| `M1_Final_Test_Report.md` | `m1_final_test_report.md` |
| `M1_Implementation_Report.md` | `m1_implementation_report.md` |
