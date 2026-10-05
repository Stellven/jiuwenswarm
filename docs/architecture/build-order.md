---
id: arch.build_order
type: plan
level: present
status: draft
version: 3
provides: [arch.build_order]
consumes: [arch.flow, arch.verification]
depends_on: [flow.md, verification.md, runtime.md, rsi.md, system/modules.md, capabilities/README.md, decisions.md, contracts/README.md, system/test-surfaces.md]
tags: [build-order, coding, start-here]
prd: [6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13]
---

# Build order: what to build, in what order, how to know it works

PRD: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13

> Answers: What do we build, in what order, and how do we know each step works?

This page is written so a coding agent can read one work package and say "I will write these [blocks](system/modules.md#term-block), to these schemas, and I am done when these tests and this demo pass."

Where this sits in the V model: [v-model](v-model.md). Each step below is a small V: block tests first, then code, then boundary tests, then the demo. [V rows](system/test-surfaces.md#term-v-row) are in [test surfaces](system/test-surfaces.md). B ids are in [modules](system/modules.md).

## Strategy

1. **Thin vertical slices.** Each step adds one block or one link and ends with a demo that [runs](system/lifecycle.md#term-run). Never build all of the blocks first and all [boundaries](system/modules.md#term-boundary) after.
2. **Fakes first, then real.** Every block is first built against fake neighbours (fake [model bridge](system/model-bridge.md#term-model-bridge) with recorded replies, fake store failures, fake clocks). Fakes use the same schemas as the real thing, so the swap changes nothing.
3. **Follow the PRD stages, with the differences listed below.** The table "Mapping to PRD stages" shows where we differ and why.
4. **Runners before [capsules](capsule/capsule.md#term-capability-capsule).** The CC tool runner and the CC skill runner are demonstrated with toy capsules before any research capability is ported.
5. **Work CC then [Gate](verification.md#term-gate) CC is demonstrated early and repeatedly.** Demos D1 to D3 must pass before any step after 4 starts. Every research capability ported later passes the same demo with its own Gate before the next one starts.
6. **CCs must become [nodes](system/nodes.md#term-node) and connect.** A [run plan](types/run-plan.md#term-run-plan) binds a CC as a node, feeds it typed inputs, runs it, gates it and passes its output on. That is demo D3, before intent or planning work.
7. **Schemas before code.** Messages are defined in [contracts](contracts/README.md). Generate types from them. If code and schema disagree, fix the schema first, in the same change.
8. **Each step has an independent check.** Expected results are written by someone other than the builder. Documentation [checks](capsule/fields.md#term-check) (lint, links) never count as a step being done.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-demo"></a>**Demo** (also: demos) | A runnable milestone D0 to D6 that ends a build step and shows one capability working end to end, for example a work capsule followed by its Gate. A step is done only when its demo passes. |

## Demonstration milestones

| Demo | What it shows | Must pass before |
|---|---|---|
| <a id="term-d0"></a>**D0** | one bounded model call through the Codex adapter and the model bridge, authenticated, captured | step 1 |
| <a id="term-d1"></a>**D1** | tool CC runs: an admitted toy tool CC is run by hash, output typed and captured, wrong input refused, timeout kills the child tree | step 3 |
| <a id="term-d1s"></a>**D1s** | skill CC runs: an admitted toy skill CC runs its model turns through the skill runner and the bridge (recorded replies), output typed and captured | step 3 |
| <a id="term-d2"></a>**D2** | work CC then Gate CC: toy node A runs, output and capture are committed by the supervisor, the verifier Gate runs right after, a passing verdict releases the next step, a failing verdict stops it. Tool kind and skill kind | step 4 |
| <a id="term-d3"></a>**D3** | two nodes connected: a frozen two-node toy plan, node A feeds node B, a Gate after each. Failure at A means B never starts. A kill leaves a halt report (INTERRUPTED) and `cc resume` continues with no result lost | step 5 |
| <a id="term-d4"></a>**D4** | prep to plan: request in, intent and Gate, requirement and Gate, template planner, validate, bind, freeze 2, planned nodes, delivery. Toy capsules | step 8 |
| <a id="term-d5"></a>**D5** | one research capability end to end with its Gate, then each next capability the same way | each later capability |
| <a id="term-d6"></a>**D6** | full research run on a small fixture; a valid scientific FAIL still produces a report. Exit of step 10; the benchmark API (V29) is built after it | step 11 |

## Mapping to PRD stages

| PRD stage | Our [steps](system/nodes.md#term-step) |
|---|---|
| 0 runtime unblocker, local configuration (6.3) | 0, plus restricted-child [probes](system/environment.md#term-probe) at step 2 |
| 1 governed execution backbone (6.4) | 1 to 4 |
| 2 intake, requirement contract, static DAG (6.5) | 4 to 7 (planner and two [freezes](system/lifecycle.md#term-freeze) replace the static DAG: Freeze 1 and 2) |
| 3 evidence to hypothesis (6.6) | 8 |
| 4 builder and POC (6.7) | 8 (POC capsule), 9 (restricted POC service) |
| 5 benchmarking and evaluation (6.8) | 9 |
| 6 delivery and end-to-end run (6.9) | minimal delivery at 7, full run at 10 |
| 7 operational shell (6.10) | 10 |
| 8 offline [RSI](rsi.md#term-rsi) (6.11) | 11 |
| 9 Phase 2 [test suites](schemas/checks.md#term-test-suite) (6.12) | 12 (non-blocking) |

### Differences from the PRD stage order

| Difference | Why |
|---|---|
| PRD stage 0 includes restricted identity. We run the doctor core at step 0 and the restricted-child probes at step 2 | probes need the confinement adapter (B20) and a real child, which exist only at step 2 |
| PRD stages 3 and 4 (evidence to hypothesis, builder and POC) are merged in our step 8 | the capsules share one Gate pattern and one demo D5 each; the restricted POC service follows in step 9 |
| Benchmark capability is built in step 9, with evaluation | it consumes the [benchmark payload](types/benchmark-payload.md#term-benchmark-payload) |
| Minimal delivery at step 7, full publication at step 10 | D4 needs an answer out before the research capabilities exist |

## Work packages

### Step 0: runtime unblocker

- **Write:** B01 configuration and installer (`cc bootstrap`), auth provider, B11 model bridge, B02 doctor core (config check and native `run_doctor`).
- **Schemas:** `services-v1.schema.json#model_bridge_request`, `#model_bridge_result`, `#model_call_scope`; `tools-v1.schema.json#config_snapshot`, `#doctor_check`, `#doctor_report`.
- **Tests:** V01, V02, V30 (core). The bridge refuses a caller without the capability token. Auth loss returns a typed error.
- **Done:** D0.

### Step 1: foundation

- **Write:** B14 store, hashes, vocabulary, [registries](schemas/policy.md#term-registry); B29 system records ([SystemRecord](system/records.md#term-systemrecord)); B15 admission validation with the tested provider; [library snapshot](capsule/library.md#term-library-snapshot), [active alias](capsule/library.md#term-alias) and rollback; bootstrap of the toy capsules (`cc bootstrap`, actor `installer`).
- **Schemas:** `library-rsi-v1.schema.json#admission_request`, `#admission_decision`, `#library_snapshot`, `#library_entry`, `#activation_request`, `#activation_record`; `tools-v1.schema.json#standing_change_request`; `execution-v1.schema.json#dispatch_reservation`, `#run_phase_started`.
- **Tests:** V03, V04, V38 (steps 1 to 3). Changed bytes are refused; a killed write leaves no partial record; rollback and a running run keeps its pinned snapshot.
- **Done:** toy tool and skill capsules admitted, activated and rolled back.

### Step 2: CC tool runner, CC skill runner and confinement

- **Write:** B09 runner and client, B10 handlers, broker and SDK, B20 confinement adapter, B23 capture collector, B24 event bus, doctor restricted-child probes (B02), minimal freeze for the toy plan (B07). Admission test calls (B15) are wired to the runner.
- **Schemas:** `execution-v1.schema.json#runner_request`, `#runner_response`, `#call_descriptor`, `#tool_host_frame`, `#skill_turn_frame`, `#model_client_call`, `#model_client_reply`, `#commit_request`, `#commit_result`, `#event_envelope`; `tools-v1.schema.json#execution_profile`.
- **Tests:** V05, V06, V07, V30 (probes), V31. The runner returns its [Observation](schemas/observation.md#term-observation) and the supervisor commits it. A timeout kills the child tree. Frames are length-prefixed.
- **Done:** D1 and D1s.

### Step 3: verifier CC and Gate host

- **Write:** B16 `research.verifier` with the toy profile, B12 [check runner](capsule/gate-host.md#term-check-runner), B13 [Gate host](capsule/gate-host.md#term-gate-host) called by `CcBackend`. Admission test calls (B15) run through the Gate path.
- **Schemas:** `execution-v1.schema.json#gate_request`, `#gate_result`, `#release_record`; `tools-v1.schema.json#run_checks_request`, `#run_checks_result`, `#check_call`, `#check_result`; types `evidence_bundle`, `verifier_assessment`.
- **Tests:** V08, V09, V10, V33, V38 (done), V40, V44. [Tier 1](verification.md#term-tier-1) failure never calls the verifier. A declared failure mode is INCONCLUSIVE and [halts](system/lifecycle.md#term-halt). A rejected admission shows the [reason code](schemas/policy.md#term-reason-code) reasons.
- **Done:** D2.

### Step 4: supervisor, launcher and SwarmFlow walking a frozen plan

- **Write:** B04 launcher on a toy plan (it needs B06 only from step 7), halt host with human review, `cc resume` and abort, headless mode with exit codes 0, 2, 3, 4, toy intake (`cc/intake.py`), B08 [Codex adapter](system/integration.md#term-codex-adapter) adapter, freeze for phase `prep` (B07), run view API (B24).
- **Schemas:** `execution-v1.schema.json#launch_request`, `#launch_result`, `#resume_request`, `#abort_request_run`, `#halt_report`, `#human_review_record`, `#run_status_view`, `#freeze_request`, `#freeze_result`, `#workflow_start_args`.
- **Tests:** V11, V35, V37, V39, V41, V42, V43. A crash never resumes by itself. Abort kills the child tree and commits the Observation. The view API refuses writes.
- **Done:** D3.

### Step 5: intake and the intent CC

- **Write:** B03 intake and snapshot, B18 [source text](types/source-text.md#term-source-text) extraction, B16 `research.compile_intent` and its profile ([intent compile](capabilities/intent-compile.md), [intent gate](capabilities/intent-gate.md)), nested review support in the runner.
- **Schemas:** types `intake`, `source_text`, `resource_snapshot`, `intent_ir`; `library-rsi-v1.schema.json#intake_request`, `#intake_result`, `#intent_fidelity_review`, `#intent_repair_record`.
- **Tests:** V12, V13, V14. Loop cases with recorded replies (pass, repair then pass, budget spent, malformed review).

### Step 6: requirement CC

- **Write:** B16 `research.compile_brief` and its profile ([requirement](capabilities/requirement-capsule.md), [brief gate](capabilities/brief-gate.md)); wire accepted `intent_ir` into it with [prep.plan.json](capabilities/prep.plan.json).
- **Schemas:** types `research_brief` and `intent_ir`; no new message defs.
- **Tests:** V15, V34. Zero requirement dispatches after a failed `G_intent`; zero planner work before `G_req` [releases](system/lifecycle.md#term-release).

### Step 7: planner, validator, planned freeze, data injection

- **Write:** B05 planner with the fixed template (no model call), B06 plan [validator](system/planner.md#term-plan-validator), freeze for phase `planned` (B07), data injection from `prep.*` sources, B19 minimal type-agnostic delivery. B04 now calls B06.
- **Schemas:** `services-v1.schema.json#planner_request`, `#planner_proposal`, `#validation_request`, `#plan_validation`; `library-rsi-v1.schema.json#deliver_request`, `#publication_manifest`, `#deliver_result`.
- **Tests:** V16, V17, V19, V36, V45, V18. Invalid plans cause zero dispatch. Wrong [port types](schemas/port-types.md#term-port-type) are refused at freeze.
- **Done:** D4 (V18).

### Step 8: search, screening, hypothesis, POC capsule

- **Write:** B17 search broker, B16 capsules for search, screening, hypothesis and POC, B18 helpers. One capability at a time, each with its Gate.
- **Schemas:** `library-rsi-v1.schema.json#poc_execute_request` ([restricted child](capsule/process-boundary.md#term-restricted-child) only), `tools-v1.schema.json#broker_search_request`, `#broker_search_result`.
- **Tests:** V20. `op.scholarly_search` declares egress but the child has no network; the egress is brokered.
- **Done:** D5 per capability.

### Step 9: restricted POC service, benchmark, evaluation, report

- **Write:** B21 generated POC service, B22 measurement service, B16 benchmark, evaluation and `research.write_report` ([write-report](capabilities/write-report.md)).
- **Schemas:** `library-rsi-v1.schema.json#poc_execute_result`, `#measurement_request`, `#measurement_result`, `#measurement_evidence`.
- **Tests:** V21, V22, V23. Exact-arithmetic evaluation checks; forged measurement refs refused.
- **Done:** D5 per capability.

### Step 10: delivery, shell and full run

- **Write:** full B19 publication, B24 CLI, web and TUI views, B23 assembler and export.
- **Schemas:** `execution-v1.schema.json#cli_json_output`, `#run_manifest`; `services-v1.schema.json#benchmark_export` stays `PENDING_SOURCE`.
- **Tests:** V24, V25, then V29 (B28 benchmark API, after D6).
- **Done:** D6.

### Step 11: offline RSI

- **Write:** B26 [fixture oracle](capsule/fixture-oracle.md#term-fixture-oracle), B25 RSI controller (needs the B23 and B28 exports), [RSI child](capsule/rsi.md#term-parent-and-child) path, admission providers, activation ([rsi](rsi.md)).
- **Schemas:** `library-rsi-v1.schema.json#rsi_start_request`, `#rsi_submit_request`, `#oracle_evaluate_request`, `#oracle_aggregate_result`, `#admission_request`, `#activation_request`.
- **Tests:** V26, V27, V28. Needs a stable parent capsule and [fixtures](system/test-surfaces.md#term-fixture) first.
- **Done:** the attack suite is blocked and logged, query counters persist, nothing activates without a human.

### Step 12: isolated experiments (non-blocking)

- **Write:** B27 experiment entry; model-planned DAGs, router, Code Mode. Mocks until access is approved.
- **Schemas:** `services-v1.schema.json#experiment_request`, `#planning_reservation`.
- **Tests:** V32. Never part of the production path.

## Working rules

- A seam is proven when the producer's real output enters the consumer and a wrong output is refused.
- The runner grows only as the next boundary needs it. Records come first, keyed by `obs_id`. Events and views come later.
- Parallel work is fine against pinned schemas. A platform probe that has not run blocks only the [execution profile](schemas/profiles.md#term-executionprofile) that needs it. Never report an unrun check as passed.
- Keep algorithms inside blocks. Output meaning, frozen policy, permissions and evidence order survive any optimization.
- Add a capsule only for independent reuse, governance or a permission boundary. Otherwise it is an [ordinary module](capabilities/README.md#term-ordinary-module).

## From these docs to code and tasks

- Every flow node has a stable ID (`N_*`, `G_*`) in [flow](flow.md). A coding task cites those IDs, the block ids, the schema defs and the demo it must pass.
- For a block, read its capability or module page, the schema defs, [runtime](runtime.md) for failure rules, and [test surfaces](system/test-surfaces.md).
- Undecided inputs are `PENDING_SOURCE` and listed in [decisions](decisions.md#open). Module placement: [modules](system/modules.md). Reused code: [integration](system/integration.md).
- Names are working names and will be consolidated with the PRD and the coding side.
