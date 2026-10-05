---
type: index
status: draft
version: 1
owner: muk
sources: [policies.md, ../product/SOURCE_FREEZE.md]
provides: [architecture.authority_index]
consumes: []
depends_on: [policies.md, types/types.md, contracts/README.md, system/modules.md, prd/coverage.md]
tags: [authority, contracts, maintenance, handoff]
---

# Find the authority before changing the design

This page is a routing index. It owns no payload fields, signatures, configuration values or runtime decisions. Start here to find the file to edit; read the linked owner to obtain the contract. [Policies](policies.md) own the change rules and [PROCESS](PROCESS.md) owns the authoring/check procedure.

## Authority map

| Question or proposed change | Owning definition | Dependent views to recheck |
|---|---|---|
| What is in M1; which received file is authoritative? | [Frozen sources](../product/SOURCE_FREEZE.md) and its manifest; [master PRD](../product/prd-m1-full-2026-10-02.txt) | [Coverage](prd/coverage.md), decisions, affected tracks and module cards |
| Why was an alternative adopted; what replaces it later? | [Decision ledger](decisions.md); the current contract remains on the linked owner page | Source trace, replacement boundary and affected consumers |
| Where does code go; who owns a component or writes a record? | [Module map](system/modules.md) for placement; each linked component for its API and effects | [Integration](system/integration.md), handoff, spatial diagram |
| Which source symbols are reused at which revision? | [Integration map](system/integration.md) | Adapters, module placement, source-specific verification obligations |
| Declaration shape and capsule identity | [Declaration](capsule/fields.md) | Author kit, admission, library, runner, freeze, capsule declarations |
| Shared Ref, EvidenceRef and Reason shapes | [Common schema](schemas/common.md) | Record/payload schemas, service imports, reference resolution and export projections |
| Payload and CC record wire fields | [Datatype index](types/types.md), linking the single field-table owner | Generated [exports](exports/manifest.json), exact-port producers/consumers, Gates, examples |
| Ordinary service wire shapes | [Service schema](contracts/services-v1.schema.json) and [schema responsibility](contracts/README.md) | The named API's semantic owner, clients, fixtures and imports |
| Policy registries and standard reason codes | [Policy](schemas/policy.md) | Declaration validation, admission, runner, Gate fold, service projections |
| Policy-selected profiles | [Profile meanings](schemas/profiles.md); any authored wire shape is explicitly delegated to the service schema | Binding, admission, Gate, execution and recovery |
| Run-plan representation and production bindings | [Run-plan type](types/run-plan.md) for fields; [pipeline](m1/pipeline.md) for the fixed production plan and capsule inventory | Freeze, planner validator, stage pages, spatial/temporal diagrams |
| Capsule execution, SDK and host frames | [Runner](capsule/runner.md) | Kind handlers, broker, model adapter, each capsule and Gate evidence |
| Gate authority and durable result fields | [Gate host](capsule/gate-host.md) for execution/fold; [Verification](schemas/verification-record.md) for fields | Profiles, lifecycle, release, stage criteria, nested calls |
| Record variants, reservations and release identity | [System records](system/records.md) | Lifecycle, storage, headless API, private RSI/controller records |
| Durable publication, record/file custody and interrupted writes | [Storage](system/storage.md) | Component writers, release/recovery, Data Foundation, retrieval/export |
| Start, stop, duplicate requests, resume or restart | [Lifecycle](system/lifecycle.md) | Launcher, runner, benchmark API, workstation, temporal diagram |
| Docker topology, volumes and host access | [Deployment](system/deployment.md) | Module/process map, environment, startup/doctor, security probes |
| Configuration keys, precedence, reload and execution profiles | [Environment](system/environment.md) | Every settings consumer, frozen manifest, export, doctor |
| Codex credentials and replaceable authentication provider | [Model authentication](system/model-auth.md) | Deployment custody, model bridge, local setup, cancellation/relogin cases |
| Scientific protocol, trusted measurements and numeric policy | [Measurement protocol](m1/measurement-protocol.md) | Blueprint, POC, scientific Benchmark, Evaluation, trusted methods |
| Per-stage product behavior and stage criteria | [Pipeline](m1/pipeline.md) links each stage owner; [research Gates](m1/research-gates.md) links checks | Payload owner, connected stages, stage profile and story |
| Offline RSI, oracle and admission/activation crossings | [RSI engine](capsule/rsi-engine.md), [fixture oracle](capsule/fixture-oracle.md), [admission](capsule/admission.md), [library](capsule/library.md) | Private records, quota/lineage, Candidate, isolation and activation cases |
| Experimental planner decisions and validation | [Planner](system/planner.md), [track isolation](system/experiments.md) | Service schema, run plan, permitted profiles, freeze and experiment evidence |
| External benchmark and local user interfaces | [Benchmark export](system/benchmark-export.md), [workstation](system/workstation.md) | Client adapters, public service envelopes, auth, record joins |
| Live events, debug traces and required evidence | [Observability](system/observability.md); required durable custody remains [storage](system/storage.md) | UI, reconstruction, Data Foundation and export |
| PRD coverage and build dependency order | [Coverage](prd/coverage.md), [build order](system/build-order.md) | Clause inventory, coder completeness, handoff |
| What remains unverified? | [Validation obligations](open-issues.md), [verification surface](system/verification.md) | Release evidence, relevant acceptance conditions and security/platform claims |

An interface can have one wire-shape owner and one semantic owner. They own different facts: the schema defines fields and constraints; the API page defines authorization, timing, effects and reference resolution. The API page links the schema rather than maintaining another field table. A summary or pseudocode shape is a reading aid, never an alternative wire contract. If the two disagree, fix both before handing that boundary to builders; do not silently choose the convenient version.

## What to edit and what to regenerate

| File class | Maintenance rule |
|---|---|
| `types/*.md`, `schemas/*.md`, `capsule/fields.md` | Edit the owning table/meaning, then regenerate exports and recheck consumers |
| `contracts/services-v1.schema.json` | Authored schema: edit directly, then update semantic owner and constructed fixtures |
| `exports/`, `graph.md`, marked generated projection examples and production data-spine view | Generated: regenerate with architecture lint; never edit by hand |
| `system/diagram-atlas.md`, `system/diagram.md`, `system/temporal.md` | Authored contract views: update affected edges/sequence, not a second definition of fields |
| `system/handoff.md`, `system/coder-requirements.md`, `stories/`, `prd/coverage.md` | Navigation and acceptance views: link owners; use concrete examples without adding rules |
| `reviews/`, dated checkpoint manifests, past check counts | Historical evidence: append a new dated result; preserve what was actually checked at the old revision |
| Frozen received files, `archive/`, old proposals/replies | Preserve origin/history; keep outside the coding authority path. Active interpretations link current owners |

The [October 3 checkpoint](handoff-checkpoint-2026-10-03.json) describes its captured revision. Later corrections do not make its hashes current. A new handoff release needs a new checkpoint/evidence record.

## Change-impact walkthrough

1. Identify the owner in this index or [datatype index](types/types.md). Record changed fields/meaning and the adoption/replacement reasoning in the decision ledger.
2. Follow `provides`, `consumes` and `depends_on` through the generated [graph](graph.md). Search the contract ID, type version, field name and API symbol to catch references not expressed in metadata. The graph is a dependency view, not proof of complete impact coverage.
3. Edit the authority. Recheck the producing and consuming boundaries, Gate, frozen pins, error behavior and persistent records affected by that change.
4. Regenerate derived schemas/graph. Update only affected diagram edges, examples, stories, coverage and handoff links. Linked navigation that still points to the correct authority requires no restated values.
5. Run the relevant architecture checks and a fresh adversarial/source review. Record observed results and unrun implementation obligations separately. Invalidate affected earlier evidence rather than treating it as a new pass.

This keeps routine changes local without hiding their actual impact. A field rename still requires all wire users to change; a prose explanation change does not require rewriting every summary.
