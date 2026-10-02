---
type: home
status: draft
tags: [types, index, m1]
depends_on: [../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
---

> **Checked, not yet approved.** Written 2026-10-01 to give every shared datatype exactly one definition.

# Payload types: one definition for every value that moves

A **payload type** is the type of a value that one module hands to another: the user's request, an IntentIR, a Research Brief. Ports name it, Artifacts carry it, and the gate checks it. Each payload type has **one page in this folder**, and that page is its only definition. Everything else links here.

The table also indexes **internal system API envelopes** owned by tool/component pages. These are not capsule port payloads or Artifact types; their single defining page is named explicitly.

## Where every shared datatype is defined

Use this table to find the one definition of anything that crosses a module boundary. If a datatype is not here, it is not shared, or it is a gap to report.

| Datatype | What it is | The one definition |
|---|---|---|
| Declaration | what a capsule promises | [capsule/fields.md](../capsule/fields.md) |
| Records: Candidate, Verdict, Standing, Binding, Observation, Artifact, Verification, Finding, test case, test suite | what CC's tools write about capsules and calls | [schemas/](../schemas/schemas.md), one page each |
| Policy and registries | every rule, default and open list | [schemas/policy.md](../schemas/policy.md) |
| Port type vocabulary | the list of type names, with each type's JSON Schema and checks | [schemas/port-types.md](../schemas/port-types.md) for its shape; **this folder** for each domain type's content |
| **Payload types** | the values capsules take and give | **this folder**, one page each |
| Check calling convention, `CheckResult` | how check code is called and what it returns | [schemas/checks.md](../schemas/checks.md#calling-convention) |
| Call descriptor, envelope, tool host frames, `cc_sdk`, model client contract | how the runner talks to Swarmflow, tool code and the model | [capsule/runner.md](../capsule/runner.md) |
| System API envelopes: `PocExecutionRequest`, `PocExecutionResult` | generated POC subprocess request and result; provisional M1 security boundary | [capsule/process-boundary.md](../capsule/process-boundary.md#provisional-api) |
| System API envelopes: `FixtureEvaluationRequest`, `FixtureEvaluationResult` | private fixture-oracle request and aggregate-only response for RSI | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md#provisional-api) |
| Capsule folder layout | what an author puts in a capsule's folder | [capsule/toolchain.md](../capsule/toolchain.md#the-capsule-folder) |
| Gate API, `GateResult`, the five verdicts | how a step is gated and what may follow | [capsule/gate-host.md](../capsule/gate-host.md) |
| AdmissionProvider and Puppet Gate | how a Candidate receives an assurance decision and enters the library | [capsule/admission.md](../capsule/admission.md) |
| Admission, Gate, retry and execution profiles | policy-selected behavior behind uniform interfaces | [schemas/profiles.md](../schemas/profiles.md) |
| Gate capsule pattern, `prompt.gate_judging` | what every gate capsule declares | [capsule/gate-capsules.md](../capsule/gate-capsules.md) |
| Run plan | which nodes run, in order, wired how, gated by what | [types/run-plan.md](run-plan.md); the M1 plan is [m1/pipeline.md](../m1/pipeline.md) |
| CC events | what the hosts announce live, and the bus | [system/observability.md](../system/observability.md#the-events) |
| Adapters to existing code | every connection to agent-core and jiuwenswarm | [system/integration.md](../system/integration.md) |
| Node model and lifecycle | what a node is, locked against planned | [system/nodes.md](../system/nodes.md) |

## The rules

1. **Every value that crosses a module boundary has a named type.** That covers capsule to capsule, control code to capsule, and capsule to control code. The type is a page here and an entry in the port type vocabulary. A port of type `json` with a `Port.value_schema` is for a value no other module reads. Freeze refuses to wire a `json` port into another capsule's port (proposed policy rule `wired_ports_named`, `PORT_TYPE_MISMATCH`).

   **Why named types, not `json` plus a schema.** Freeze checks a wiring by comparing type names (`PORT_TYPE_MISMATCH`). Selection chains capsules by type name, and Symphony matches `CapabilityIO.type` by name ([port types](../schemas/port-types.md)). Two `json` ports with different schemas compare equal by name, so a wrong wiring would pass every check. One named type gives one schema that producer and consumer both pin, through the vocabulary the Binding pins.

2. **The page is the source; the JSON Schema is generated.** A type page's field table uses the type grammar of the [invariants](../schemas/invariants.md). The vocabulary builder ([toolchain](../capsule/toolchain.md#vocabulary-builder)) compiles each table into the type's `value_schema`. Nobody writes a payload type's JSON Schema by hand, so the page and the schema cannot drift. The generation rules:

   | Grammar | JSON Schema |
   |---|---|
   | `string`, `text` | `{"type": "string"}`; a `req` `text` field also has `"pattern": "\\S"` |
   | `id` | `{"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"}` |
   | `integer`, `number`, `boolean` | the JSON type |
   | `sha256` | `{"type": "string", "pattern": "^[0-9a-f]{64}$"}` |
   | `enum(a, b)` | `{"enum": ["a", "b"]}` |
   | `reg(name)` | `{"type": "string"}`. Membership is checked by `check.value_matches_type.v1` against registry `name` of the policy the Binding pins, so registry values have one source, the policy |
   | `list<T>` | `{"type": "array", "items": T}` |
   | `map<string, T>` | `{"type": "object", "additionalProperties": T}` |
   | `object` | `{"type": "object", "additionalProperties": false}`, with its `parent.child` rows as properties |
   | `list<object>` | `{"type": "array", "items": O}`, where `O` is the closed object built from its `parent[].child` rows |
   | `Reason`, `EvidenceRef`, `Check` | the closed object of that shape's rows on [common](../schemas/common.md) or [fields](../capsule/fields.md#checks-one-runnable-test-each), compiled by these same rules |
   | a `list<...>` whose description starts `At least one.` | adds `"minItems": 1` |
   | `json` | any JSON value |
   | `T?` | `T` or `null` |
   | `req` / `opt` | listed in `required` / not listed |

   The type's name is the code span in the page's title; its `version` is the front matter's `version`; its vocabulary `description` is the page's first sentence. A rule written only in a description (such as "Always `prompt`") is not compiled; it must be a check.

3. **Closed core, open `ext`.** Every payload object is closed: a field the page does not name is refused. The top level of every payload type also allows one optional field, `ext` (`map<string, json>`), keyed by producer, for anything extra (INV-14, applied to values). A consumer may read only the fields on the page. So nobody relies on a field that nobody declared.

4. **No copies of facts another record holds** (INV-5). A payload never repeats its own type or version (the Artifact's `type` and the pinned vocabulary say it), who produced it, or when (the Observation says it).

5. **Versions are immutable.** Once a payload version is published, no core field is added, removed, renamed, narrowed or reinterpreted. Producer-specific same-version additions go only under `ext`. Any core-shape or meaning change creates a new type version and an explicit adapter capsule where old and new versions must connect. The vocabulary itself also receives a new `vocabulary_version`, pinned by Verdict and Binding. This is the local form of versioned schema compatibility and explicit migration used by [Confluent Schema Registry](https://docs.confluent.io/platform/current/schema-registry/fundamentals/data-contracts.html).

6. **Type checks.** A type page lists the checks every value of that type must pass, in a table with every column a Check needs: id, anchor, over, applies at, runner, author, and what passes (the target is the type). They are registry checks, written in full in the vocabulary, with `check.value_matches_type.v1` always first. The gate runs them on every output of the type, and `record_input` runs the deterministic ones before it stores a value. Their code lives in the CC repository's check library ([toolchain](../capsule/toolchain.md#where-code-lives)), written by someone other than the producing capsule's author (INV-10).

7. **Who owns what.** Architecture owns these pages: the fields, their types and the checks. The product meaning of a stage's output comes from the PRD, and PRD section 6, "Payload Specs", is expected to own it once it exists. Until then these pages are the proposal. A change goes through a change to the page, never through a capsule's own files.

## The M1 payload types

| Type | Version | Status | Made by | Read by |
|---|---|---|---|---|
| [`intake`](intake.md) | 2 | draft | M01 launcher, through `record_input` (`origin: human`) | `intent` step, `requirement` step |
| [`source_text`](source-text.md) | 1 | draft | `research.extract_text` or a direct-text launcher | `research.compile_intent` and other text capabilities |
| [`resource_snapshot`](resource-snapshot.md) | 1 | draft | launcher/store snapshot service | Search, Hypothesis, POC and Benchmark |
| [`dependency_requirement`](dependency-requirement.md), [`dependency_assessment`](dependency-assessment.md) | 1 | draft | Screening and the pinned dependency policy | deterministic opportunity ranking; Hypothesis context |
| [`intent_ir`](intent-ir.md) | 1 | draft | `research.compile_intent` | `requirement` step |
| [`research_brief`](research-brief.md) | 1 | draft; three open questions in [open issues](../open-issues.md) | `research.compile_brief` | every later step |
| [`idea_set`](idea-set.md), [`search_hits`](search-hits.md) | 1 | checked | search, and its operators | screening; `research.search_ideas` |
| [`screening_assessments`](screening-assessments.md) | 2 | draft; internal typed call input, not a pipeline Artifact | `research.select_opportunity` | `op.rank_opportunities` |
| [`opportunity_card`](opportunity-card.md) | 2 | draft | Screening | Hypothesis and Report |
| [`hypothesis_blueprint`](hypothesis-blueprint.md), [`poc_bundle`](poc-bundle.md), [`benchmark_payload`](benchmark-payload.md), [`evaluation_verdict`](evaluation-verdict.md), [`research_report`](research-report.md) | 2 | draft/provisional; policy and deployment blockers on owning pages | Hypothesis through Report | downstream work and independent Gates |
| [`code_hits`](code-hits.md) | 1 | draft | op.codesearch | Hypothesis and POC |
| [`evidence_bundle`](evidence-bundle.md) | 1 | draft | M10 gate host | the step's gate capsule, named in the Binding's `verifier` |
| [`verifier_assessment`](verifier-assessment.md) | 1 | draft | the step's gate capsule | M10a, which writes it into the Verification through M10 |
| [`run_plan`](run-plan.md) | 1 | draft | the launcher; later, a planner capsule | freeze, the generic script |

**Draft/checked/locked are review and approval states** as defined in [PROCESS](../PROCESS.md). A canonical schema version does not imply Muk approval or an executed acceptance result.

## The M1 steps that use them

Which node makes and reads each type, step by step, is defined once in [the M1 pipeline](../m1/pipeline.md).

## Added system contracts

| Contract | Canonical owner |
|---|---|
| Module paths/processes and seven handoff questions | [modules](../system/modules.md) |
| Durable publication, required capture and EvidenceManifestRef | [storage](../system/storage.md) |
| SystemRecord, SystemRef, dispatch reservations and release | [system records](../system/records.md) |
| RunnerRequest/Response, explicit recovery and human session | [lifecycle](../system/lifecycle.md) |
| ConfigSnapshot, ModelBridgeRequest/Result, DoctorReport, platform profile | [environment](../system/environment.md) |
| CLI/Web/TUI RunView and local token/session file | [workstation](../system/workstation.md) |
| BenchmarkSample, MeasurementEvidence, registry, syntax and snapshot operators | [measurement protocol](../m1/measurement-protocol.md) |
| StageContext and report template adaptation | [Delivery](../m1/delivery.md) |
| RsiSessionResult and Attempt entry | [RSI engine](../capsule/rsi-engine.md) |
| code_hits payload, version 1 | [code hits](code-hits.md) |
| source_text, resource_snapshot and dependency payloads | [source text](source-text.md), [resource snapshot](resource-snapshot.md), [requirement](dependency-requirement.md), [assessment](dependency-assessment.md) |

Hypothesis, POC, Benchmark, Evaluation and Report payloads are now version 2. Their owning pages are canonical; product policy and deployment blockers are listed there. Capsule-level APIs use these types directly; internal envelopes are not alternate payload-schema copies.
