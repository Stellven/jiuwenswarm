---
type: home
status: draft
tags: [types, index, m1]
depends_on: [../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
prd: []
prd_note: index of payload types; no single PRD clause
id: types.types
level: detail
---

# Payload types: one definition for every value that moves

A **payload type** is the type of a value that one module hands to another: the user's request, an [IntentIR](intent-ir.md#term-intentir), a [Research Brief](research-brief.md#term-research-brief). Ports name it, [Artifacts](../schemas/artifact.md#term-artifact) carry it, and the gate [checks](../capsule/fields.md#term-check) it. Each payload type has **one page in this folder**, and that page is its only definition. Everything else links here.

The table also indexes **internal system API envelopes** owned by tool/component pages. These are not [capsule](../capsule/capsule.md#term-capability-capsule) port payloads or Artifact types; their single defining page is named explicitly.

## Where every shared datatype is defined

Use this table to find the one definition of anything that crosses a module boundary. If a datatype is not here, it is not shared, or it is a gap to report.

| Datatype | What it is | The one definition |
|---|---|---|
| [Declaration](../capsule/fields.md#term-declaration) | what a capsule promises | [capsule/fields.md](../capsule/fields.md) |
| Records: Candidate, Verdict, Standing, [Binding](../schemas/binding.md#term-binding), [Observation](../schemas/observation.md#term-observation), Artifact, [Verification](../schemas/verification-record.md#term-verification), Finding, [test case](../schemas/checks.md#term-test-case), [test suite](../schemas/checks.md#term-test-suite) | what CC's tools write about capsules and calls | [schemas/](../schemas/schemas.md), one page each |
| Policy and [registries](../schemas/policy.md#term-registry) | every rule, default and open list | [schemas/policy.md](../schemas/policy.md) |
| Port type vocabulary | the list of type names, with each type's JSON Schema and checks | [schemas/port-types.md](../schemas/port-types.md) for its shape; **this folder** for each domain type's content |
| <a id="term-payload-types"></a>**Payload types** | the values capsules take and give | **this folder**, one page each |
| Check calling convention, `CheckResult` | how check code is called and what it returns | [schemas/checks.md](../schemas/checks.md#calling-convention) |
| Call descriptor, envelope, tool host frames, `cc_sdk`, model client contract | how the runner talks to [Swarmflow](../system/integration.md#term-swarmflow), tool code and the model | [capsule/runner.md](../capsule/runner.md) |
| System API envelopes: `PocExecutionRequest`, `PocExecutionResult` | generated POC subprocess request and result; provisional M1 security boundary | [capsule/process-boundary.md](../capsule/process-boundary.md#interface-provisional-api) |
| System API envelopes: `FixtureEvaluationRequest`, `FixtureEvaluationResult` | private fixture-oracle request and aggregate-only response for [RSI](../rsi.md#term-rsi) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md#interface-closed-api-envelopes) |
| Capsule folder layout | what an author puts in a capsule's folder | [capsule/toolchain.md](../capsule/toolchain.md#the-capsule-folder) |
| [Gate](../verification.md#term-gate) API, `GateResult`, the five verdicts | how a node is gated and what may follow | [capsule/gate-host.md](../capsule/gate-host.md) |
| AdmissionProvider and [Puppet Gate](../capsule/admission.md#term-puppet-admission) | how a Candidate receives an assurance decision and enters the library | [capsule/admission.md](../capsule/admission.md) |
| Admission, Gate, retry and execution profiles | policy-selected behavior behind uniform interfaces | [schemas/profiles.md](../schemas/profiles.md) |
| Shared `research.verifier` and stage Gate profiles | one semantic verifier contract | [capsule/gate-capsules.md](../capsule/gate-capsules.md) |
| Run plan | which [nodes](../system/nodes.md#term-node) run, in order, wired how, gated by what | [types/run-plan.md](run-plan.md); the research chain template is in [capabilities](../capabilities/README.md) |
| CC events | what the hosts announce live, and the bus | [system/observability.md](../system/observability.md#interface-the-events) |
| Adapters to existing code | every connection to agent-core and jiuwenswarm | [system/integration.md](../system/integration.md) |
| Node model and lifecycle | what a node is, locked against planned | [system/nodes.md](../system/nodes.md) |

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-payload-type"></a>**payload type** (also: payload types) | The type of a value that one module hands to another, such as the user's request, an IntentIR or a Research Brief. Each has one page in this folder, which is its only definition. |
| <a id="term-closed-type"></a>**closed type** (also: closed core) | A payload type whose objects refuse any field the page does not name. Only the optional top-level `ext` map allows extras, and a released version never changes its core fields. |

## The rules

1. **Every value that crosses a module boundary has a named type.** That covers capsule to capsule, control code to capsule, and capsule to control code. The type is a page here and an entry in the [port type vocabulary](../schemas/port-types.md#term-port-type). A port of type `json` with a `Port.value_schema` is for a value no other module reads. Freeze refuses to wire a `json` port into another capsule's port (proposed policy rule `wired_ports_named`, `PORT_TYPE_MISMATCH`).

   **Why named types, not `json` plus a schema.** Freeze checks a wiring by comparing type names (`PORT_TYPE_MISMATCH`). Selection chains capsules by type name, and Symphony matches `CapabilityIO.type` by name ([port types](../schemas/port-types.md)). Two `json` [ports](../capsule/fields.md#term-port) with different schemas compare equal by name, so a wrong wiring would pass every check. One named type gives one schema that producer and consumer both pin, through the vocabulary the Binding pins.

2. **The page is the source; the JSON Schema is generated.** A type page's field table uses the type grammar of the [invariants](../schemas/invariants.md). The vocabulary builder ([toolchain](../capsule/toolchain.md#m00a-vocabulary-builder)) compiles each table into the type's `value_schema`. Nobody writes a payload type's JSON Schema by hand, so the page and the schema cannot drift. The generation rules:

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

5. **Released versions are immutable.** Draft schema revisions may change together with all affected producers/consumers before a handoff release. Once a payload version is [released](../system/lifecycle.md#term-release), no core field is added, removed, renamed, narrowed or reinterpreted. Producer-specific same-version additions go only under `ext`. Any core-shape or meaning change creates a new type version and an explicit typed adapter where old and new versions must connect. The vocabulary itself also receives a new `vocabulary_version`, pinned by Verdict and Binding. This is the local form of versioned schema compatibility and explicit migration used by [Confluent Schema Registry](https://docs.confluent.io/platform/current/schema-registry/fundamentals/data-contracts.html).

6. **Type checks.** A type page lists the checks every value of that type must pass, in a table with every column a Check needs: id, anchor, over, applies at, runner, author, and what passes (the target is the type). They are registry checks, written in full in the vocabulary, with `check.value_matches_type.v1` always first. The gate [runs](../system/lifecycle.md#term-run) them on every output of the type, and `record_input` runs the deterministic ones before it stores a value. Their code lives in the CC repository's check library ([toolchain](../capsule/toolchain.md#where-code-lives)), written by someone other than the producing capsule's author (INV-10).

7. **Who decides what.** These pages decide the fields, their types and the checks. The product meaning of a stage's output comes from the PRD, and PRD section 6, "Payload Specs", is expected to own it once it exists. Until then these pages are the proposal. A change goes through a change to the page, never through a capsule's own files.

## The M1 payload types

| Type | Version | Status | Made by | Read by |
|---|---|---|---|---|
| [`intake`](intake.md) | 2 | draft | intake, through `record_input` (`origin: human`) | source projection, requirement CC, task nodes taking resources |
| [`source_text`](source-text.md) | 1 | draft | ordinary intake projection | `research.compile_brief` and experimental text consumers |
| [`resource_snapshot`](resource-snapshot.md) | 1 | draft | intake/store [snapshot](../capsule/library.md#term-library-snapshot) service | Search, Hypothesis, POC and Benchmark |
| [`dependency_requirement`](dependency-requirement.md), [`dependency_assessment`](dependency-assessment.md) | 1 | draft | Screening and the pinned dependency policy | deterministic opportunity ranking; Hypothesis context |
| [`intent_ir`](intent-ir.md) | 1 | draft | `research.compile_intent` | `research.compile_brief` (required, accepted) |
| [`research_brief`](research-brief.md) | 1 | draft | `research.compile_brief` | every later step |
| [`idea_set`](idea-set.md), [`search_hits`](search-hits.md) | 1 | checked | search, and its [operators](../capabilities/README.md#term-operator) | screening; `research.search_ideas` |
| [`screening_assessments`](screening-assessments.md) | 2 | draft; internal typed call input, not a flow Artifact | `research.select_opportunity` | `op.rank_opportunities` |
| [`opportunity_card`](opportunity-card.md) | 2 | draft | Screening | Hypothesis and Report |
| [`hypothesis_blueprint`](hypothesis-blueprint.md), [`poc_bundle`](poc-bundle.md), [`benchmark_payload`](benchmark-payload.md), [`evaluation_verdict`](evaluation-verdict.md), [`research_report`](research-report.md) | 2 | draft/provisional; policy and deployment blockers on owning pages | Hypothesis through Report | downstream work and independent Gates |
| [`code_hits`](code-hits.md) | 1 | draft | op.codesearch | Hypothesis and POC |
| [`evidence_bundle`](evidence-bundle.md) | 1 | draft | M10 gate host | shared [research.verifier](../capsule/gate-capsules.md#term-verifier), named in the Binding's `verifier` |
| [`verifier_assessment`](verifier-assessment.md) | 1 | draft | the shared `research.verifier` (stage profile) | M10a, which writes it into the Verification through M10 |
| [`run_plan`](run-plan.md) | 1 | draft | intake ([fixed prep plan](../system/lifecycle.md#term-prep-plan)); planner service ([task DAG](run-plan.md#term-planned-plan)) | freeze, the generic script |

Draft/checked/locked are status labels in each page's front matter. A canonical schema version does not imply an executed acceptance result.

## The nodes that use them

Which node makes and reads each type is defined once in [flow](../flow.md) and the [capabilities inventory](../capabilities/README.md).

## Added system contracts

| Contract | Canonical page |
|---|---|
| Module paths/processes and seven handoff questions | [modules](../system/modules.md) |
| Durable publication, required capture and EvidenceManifestRef | [storage](../system/storage.md) |
| [SystemRecord](../system/records.md#term-systemrecord), [SystemRef](../system/records.md#term-systemref), dispatch reservations and release | [system records](../system/records.md) |
| RunnerRequest/Response, explicit recovery and human session | [lifecycle](../system/lifecycle.md) |
| [ConfigSnapshot](../system/environment.md#term-configsnapshot), ModelBridgeRequest/Result, DoctorReport, platform profile | [environment](../system/environment.md) |
| CLI/Web/TUI RunView and local token/session file | [workstation](../system/workstation.md) |
| BenchmarkSample, MeasurementEvidence, registry, syntax and snapshot operators | [measurement protocol](../capabilities/measurement-protocol.md) |
| [StageContext](../capabilities/write-report.md#term-stagecontext) and report template adaptation | [Write report](../capabilities/write-report.md) |
| RsiSessionResult and Attempt entry | [RSI engine](../capsule/rsi-engine.md) |
| [code_hits](code-hits.md#term-code-hits) payload, version 1 | [code hits](code-hits.md) |
| [source_text](source-text.md#term-source-text), [resource_snapshot](resource-snapshot.md#term-resource-snapshot) and dependency payloads | [source text](source-text.md), [resource snapshot](resource-snapshot.md), [requirement](dependency-requirement.md), [assessment](dependency-assessment.md) |

Hypothesis, POC, Benchmark, Evaluation and Report payloads are now version 2. Their owning pages are canonical; required deployment validation is listed there. Capsule-level APIs use these types directly; internal envelopes are not alternate payload-schema copies.
