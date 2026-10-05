---
id: system.seams
type: design
status: proposed
version: 2
tags: [design, seams, m1]
level: detail
provides: []
depends_on: [../verification.md, ../placement.md, ../rsi.md, ../types/types.md]
prd: [4.1.4, 4.2.2]
---

# Seams: where each workstream meets Capability Capsule

PRD: 4.1.4, 4.2.2

> Answers: Where does each workstream meet Capability Capsule?

A **seam** is an API between two modules built separately. Each row says who calls whom, with what datatype, and which page defines it. Both sides build to the seam and nothing else. Every datatype named here has exactly one definition, listed in [where every shared datatype is defined](../types/types.md#where-every-shared-datatype-is-defined). A seam never redefines one.

## Seam index

| Seam | Caller | Callee | API | Datatypes | Home page |
|---|---|---|---|---|---|
| Workflow to runner | [SwarmFlow](integration.md#term-swarmflow) script, then `CcBackend` (supervisor) | runner | `cc_node`, `CcBackend.run`, `runner_request`; `record_input` is a supervisor-side control function | `intake`; call descriptor; envelope | [runner](../capsule/runner-broker.md#swarmflow-backend-talking-to-the-engine) |
| Runner to supervisor commit | runner | supervisor (only store writer) | `commit_request`, `commit_result` | [Artifacts](../schemas/artifact.md#term-artifact), [Observation](../schemas/observation.md#term-observation), capture | [runner](../capsule/runner.md#commit-path-the-supervisor-is-the-only-writer) |
| Supervisor to [Gate host](../capsule/gate-host.md#term-gate-host) | `CcBackend` (supervisor), after the runner commit | [Gate](../verification.md#term-gate) host (M10) | `gate(obs_ref) -> GateResult` | Observation, [GateProfile](../schemas/profiles.md#term-gateprofile), the five verdicts | [gate host](../capsule/gate-host.md), [verification](../verification.md) |
| Gate host to verifier | Gate host | `research.verifier` CC, through the runner | a `gate` call using the pinned Gate profile | `evidence_bundle`, `verifier_assessment` | [gate capsules](../capsule/gate-capsules.md), [verification](../verification.md) |
| Check code to [check runner](../capsule/gate-host.md#term-check-runner) | Check runner (M10a) | any check | the check calling convention | `CheckResult` | [checks](../schemas/checks.md#calling-convention) |
| Runner to [Model bridge](model-bridge.md#term-model-bridge) | runner broker (the experiment planner only in the isolated track) | model bridge (M05) | `complete(prompt, ...)` | `ModelReply`, call context | [model bridge](model-bridge.md), [placement](../placement.md#model-routing-in-one-view), [model routing](../model-routing/README.md) |
| Supervisor to planner, [validator](planner.md#term-plan-validator), binder | supervisor | planner service, plan validator, binder | candidate DAG, then [frozen](lifecycle.md#term-freeze) bound DAG | `run_plan`, [Bindings](../schemas/binding.md#term-binding) | [planner](planner.md), [run plan](../types/run-plan.md) |
| Records to [Data Foundation](storage.md#term-data-foundation) | Data Foundation assembler | record store (M12), runner events | read only | every CC record | [Data Foundation](#data-foundation) |
| [RSI](../rsi.md#term-rsi) to the library | RSI controller | Admission (M14) | submit a Candidate | Candidate, Standing, [Findings](../schemas/finding.md#term-finding) | [rsi](../rsi.md), [RSI engine](../capsule/rsi-engine.md) |
| Benchmark harness to CC | external harness | benchmark API | `run_task`, `export_run` | `benchmark_request`, `benchmark_export` | [benchmark export](benchmark-export.md) |

Verifier criteria and PRD 4.2 inputs: [verification](../verification.md), [PRD verifier](../../product/prd-m1-verifier.txt), [verifier model proposal](../../product/verifier-model-selection-proposal-2026-10-02.md). [Model routing](../model-routing/README.md#term-model-routing): [placement](../placement.md#model-routing-in-one-view), [model routing](../model-routing/README.md), [router design](../model_router_design_en.md), [routing PRD](../../product/prd-m1-model-routing.txt). Offline RSI: [rsi](../rsi.md), [RSI PRD](../../product/prd-m1-rsi-full.md).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-seam"></a>**Seam** (also: seams) | An API between two modules that are built separately. Each seam names the caller, callee, API, datatypes and home page, and is proven by real output entering the consumer and a wrong output being refused. |

## Data Foundation

Data Foundation ([PRD](../../product/prd-m1-data-foundation.md), [technical design](../data-foundation/capsule-run-records.md)). Data Foundation observes; it never changes a run.

**The seam in one line:** CC's records are the source of truth for every [capsule](../capsule/capsule.md#term-capability-capsule) call; Data Foundation's Capsule Run Record is a **view** its assembler builds from them, plus the raw material only Data Foundation captures.

### Settled here, against the run records design

| Design question (its section 10) | Answer | Why |
|---|---|---|
| Q1: which files make up a capsule, and what identifies a version | **`decl_hash`.** The [Declaration](../capsule/fields.md#term-declaration) names every file by hash: code (`carrier` or `body`), each check's `runner`, and each `Port.value_schema`. So `decl_hash` changes whenever any of them changes. `code_sha256` identifies the code alone | one identity for a capsule version across every record (INV-6). A second "hash over all files" would be a copy that could disagree |
| Q2: is each stage's capsule fixed, or does the router select it | **Fixed by the frozen [run plan](../types/run-plan.md#term-run-plan). The planner picks the capsule; the router never does.** `selected_by` is always the plan. A router only picks a model inside a capsule call | CC decides what is done; routing makes it better ([model routing](../placement.md#model-routing-in-one-view)) |
| Q3: do capsules run through one shared wrapper | **Yes: the [CC runner](../capsule/runner.md#term-runner).** Its events (R8) are the live hooks; Data Foundation subscribes to them | every capsule call has an Observation, including calls that never reach the gate |
| Q4: does the gate give per-check results | **Yes:** [Verification](../schemas/verification-record.md#term-verification) `results[]`, one per check, with `runner_sha256` and evidence | |
| Q5: native `verify()` or a [verifier capsule](../capsule/gate-capsules.md#term-verifier) | **The `research.verifier` CC**, called through the runner by the Gate host | `verify()` returns votes, not per-check results |
| Q10: can a capsule call another, and who holds the record | **Yes, through the broker.** Each call has its own Observation; a nested one names its caller in `causation_id`. The node's record is its `dispatch` Observation | |
| record key | **`obs_id`**, not a Swarmflow `agent_id` | under `CcBackend` an `agent()` call starts no team worker, so no `agent_id` or `member_name` exists. The engine's `call_key` is kept in `ext.runner.engine_call_key` |
| `label` rule | **`label` is the `step_id`.** The call descriptor carries `decl_hash` and input hashes, so the journal re-runs a step when its capsule changes | same effect as `<capsule>@<hash>`, with the version in one place |
| storage | CC records in M12 are the source. `records/records.jsonl`, bundles, scorecard and exports are Data Foundation's derived outputs, rebuildable from the record store (M12) plus its raw captures | one writer per record [kind](../capsule/capsule.md#term-capsule-kind) (INV-3) |
| prompt as sent | the runner returns every model [turn](model-bridge.md#term-model-turn)'s prompt and reply as content, committed by the supervisor and listed in the Observation's `ext.runner.turns` ([runner](../capsule/runner-broker.md#records-the-runner-returns-for-commit)) | the bundle can be rebuilt byte for byte |
| sample run export, and M1 architecture's M17 fixture export | **one export, defined by Data Foundation.** M17 is retired in its favour | two exports of the same [runs](lifecycle.md#term-run) would drift |

### Where each run record group comes from

| Run record group | Source of truth | Captured by |
|---|---|---|
| Identity: run, step, attempt, times | Observation `scope.run_id`, Binding `step_id`, `attempt`, `started_at`, `at` | runner builds it, supervisor commits it |
| Capsule: name, kind, version | Binding `decl_hash`; the Declaration's `identity` | admission, freeze |
| Given and produced | Observation `inputs`, `outputs`; Artifacts by `content_sha256` | runner |
| Lineage | Artifact `produced_by`; Observation `inputs`; nested `causation_id` | runner |
| Model and route | Observation `models`; `ext.runner.turns[].model_hint`, `.model_id`, `.route_record_id`; the router's own records | runner, router |
| Cost | Observation `cost`; the router's token counts | runner, router |
| Gate | Verification results, decision and durable gate_result; judge Observation and required capture | gate host, runner |
| How it stopped, what went wrong | Observation `outcome`, `reason`, `ext.runner.failure_code`, `error_detail` | runner |
| Failure class | **derived, never stored.** `runtime`-owned reason: `infrastructure`. `PORT_MISMATCH`, `PRECONDITION_FAILED`, `PRECONDITION_DEFERRED` or an `input`-owned code: `input`. Other refusals: `infrastructure`. `capsule`-owned reason, or a failing `capsule` check: `capsule`. A `fail` classification in `evaluation_verdict`: `scientific` | Data Foundation's assembler |
| Environment, host, workspaces, traces, tool calls, human answers | acknowledged immutable execution manifests; required capture loss [halts](lifecycle.md#term-halt) the run | Data Foundation collector; supervisor for human review |
| Declared against observed | required runner/broker/process capture fills Observation.effects_observed and compares against the frozen Declaration/profile before ok; Data Foundation projects evidence | runner; Data Foundation projection |

**Adopted span mapping:** CC records and explicit CC spans identify non-team calls by [obs_id](observability.md#term-obs-id); native worker names are optional adapter metadata. The first runtime verifies native display compatibility. Missing native spans do not remove required capture or authoritative records.

## Ingestion

The launcher reads the input folder and the prompt, builds one [`intake`](../types/intake.md) value, and stores it with the supervisor-side control function `record_input(run_id, "intake", vocabulary_ref=..., value=..., origin="human")` (not a runner operation). PRD 3.1.4 sends file paths, sizes and times to "the Swarmflow telemetry log": the `intake` value holds paths and sizes, and the Artifact's `at` holds the time.
