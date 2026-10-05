---
id: cap.index
type: index
level: detail
status: draft
version: 2
provides: [cap.inventory]
consumes: [arch.terms, arch.flow]
depends_on: [../terms.md, ../flow.md, ../capsule/capsule.md, ../types/types.md, research-template.plan.json, write-report.md, delivery.md]
tags: [capabilities, inventory]
prd: [4.1.1, 4.1.3, 4.1.4, 4.2.1, 4.8.2]
---

# Capabilities: every CC, and what is not one

PRD: 4.1.1, 4.1.3, 4.1.4, 4.2.1, 4.8.2

This page is the home of the **inventory**. Counts elsewhere are derived from this table and are not stated as targets. A [Capability Capsule](../capsule/capsule.md#term-capability-capsule) exists only where independent reuse, governance or a permission boundary needs a [Declaration](../capsule/fields.md#term-declaration). Everything else is an ordinary module ([terms](../terms.md)).

## Capability Capsules

| Identity | Kind | Role in flow | Page | Takes → gives | [Gate](../verification.md#term-gate) | M1 [RSI](../rsi.md#term-rsi) |
|---|---|---|---|---|---|---|
| `research.compile_intent` | tool, model-backed | `N_intent` | [intent-compile](intent-compile.md) | [source_text](../types/source-text.md#term-source-text) → [IntentIR](../types/intent-ir.md#term-intentir) | `research.accept_intent.v1` ([gate](intent-gate.md)) | **code and prompts** |
| `research.compile_brief` | skill | `N_req` | [requirement-capsule](requirement-capsule.md) | accepted intent, intake, source_text → [research_brief](../types/research-brief.md#term-research-brief) | `research.accept_brief.v1` ([gate](brief-gate.md)) | none |
| `research.search_ideas` | tool | task node | [search-capsule](search-capsule.md) | research_brief, intake → [idea_set](../types/idea-set.md#term-idea-set) | `research.accept_ideas.v1` ([gate](search-gate.md)) | none |
| `research.select_opportunity` | tool | task node | [screening](screening.md) | idea_set, research_brief → [opportunity_card](../types/opportunity-card.md#term-opportunity-card) | `research.accept_card.v1` ([gate](screening-gate.md)) | **Targets 1 and 2** |
| `research.form_hypothesis` | tool | task node | [hypothesis](hypothesis.md) | opportunity_card, research_brief, intake → [hypothesis_blueprint](../types/hypothesis-blueprint.md#term-hypothesis-blueprint) | `research.accept_hypothesis.v1` | none |
| `research.build_poc` | tool | task node | [poc](poc.md) | hypothesis_blueprint, research_brief, intake → [poc_bundle](../types/poc-bundle.md#term-poc-bundle) | `research.accept_poc.v1` | none |
| `research.run_benchmark` | tool, no model | task node | [benchmark](benchmark.md) | poc_bundle, hypothesis_blueprint → [benchmark_payload](../types/benchmark-payload.md#term-benchmark-payload) | `research.accept_benchmark.v1` | none |
| `research.evaluate_results` | tool | task node | [evaluation](evaluation.md) | benchmark_payload, hypothesis_blueprint, research_brief → [evaluation_verdict](../types/evaluation-verdict.md#term-evaluation-verdict) | `research.accept_evaluation.v1` | none |
| `research.write_report` | skill | task node | [write-report](write-report.md) | verdict, payload, brief, ideas, card, blueprint → [research_report](../types/research-report.md#term-research-report) | `research.accept_report.v1` | none |
| `research.verifier` | skill | every Gate | [gate capsules](../capsule/gate-capsules.md) | [evidence_bundle](../types/evidence-bundle.md#term-evidence-bundle) → [verifier_assessment](../types/verifier-assessment.md#term-verifier-assessment) | n/a (it is the verifier) | **never** |
| `op.local_search` | tool | nested in search | [op-local-search](op-local-search.md) | query, documents → [search_hits](../types/search-hits.md#term-search-hits) | mechanical | none |
| `op.scholarly_search` | tool | nested in search | [op-scholarly-search](op-scholarly-search.md) | query → search_hits | mechanical | none |
| `op.codesearch` | tool | nested in hypothesis, POC | [op-codesearch](op-codesearch.md) | query, repo [snapshot](../capsule/library.md#term-library-snapshot) → [code_hits](../types/code-hits.md#term-code-hits) | mechanical | none |

Gate criteria for research stages: [research gates](research-gates.md). Stage criteria pages are profiles of the one [verifier capsule](../capsule/gate-capsules.md#term-verifier), not separate verifier capsules.

**Today: 13 identities** (intent, brief, seven research work, verifier, three operators). The intent step uses `research.compile_intent` plus the shared verifier with the intent profile, so no new identity. Re-derive it from this table, not from other pages.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-work-capsule"></a>**work capsule** (also: work capsules, stage capsule) | A capsule that produces a stage's output, such as `research.compile_brief` or `research.build_poc`, as opposed to the verifier that judges it. Its Gate is a profile of the shared verifier, not a separate capsule. |
| <a id="term-operator"></a>**operator** (also: operators) | A small reusable `op.*` capsule that a work capsule calls as a nested call through the broker, such as a search or code-search helper. |
| <a id="term-ordinary-module"></a>**ordinary module** (also: ordinary modules) | Control code with no Declaration, no RSI and no Gate, kept as plain code because nothing needs it to be an independently governed capability. Examples are intake, the planner, delivery and the extraction helpers. |

## Ordinary modules (not capsules)

| Module | Page |
|---|---|
| source extraction (`.txt`, `.md`, `.pdf`) | [extract-text](extract-text.md) |
| ranking and [dependency assessment](../types/dependency-assessment.md#term-dependency-assessment) helpers | [rank](op-rank-opportunities.md), [dependency](op-assess-dependency.md) |
| workspace read/write helper | [workspace](op-workspace-io.md) |
| measurement transforms and trusted methods | [measurement protocol](measurement-protocol.md) |
| intake, resource freezing, planner, [validator](../system/planner.md#term-plan-validator), binder, supervisor, [Gate host](../capsule/gate-host.md#term-gate-host) | [modules](../system/modules.md) |
| delivery: renders `research_report.md` and the POC zip, publishes `outputs/<run_id>/`, records the [delivery manifest](delivery.md#term-publication-manifest) (no Gate) | [delivery](delivery.md) |

## Example plan: the research chain

The research chain is one **capability set** a planner can compose, not the whole system. The first planner emits this chain as a fixed template ([build order](../build-order.md), step 7). Machine-readable forms: [prep.plan.json](prep.plan.json) and [research-template.plan.json](research-template.plan.json). It conforms to the [run plan type](../types/run-plan.md).

```mermaid
flowchart LR
  REQ["research.compile_brief"] --> S["search_ideas"] --> SC["select_opportunity"] --> H["form_hypothesis"] --> P["build_poc"] --> B["run_benchmark"] --> E["evaluate_results"] --> W["write_report"]
```

Each arrow is a typed port connection; every box has its own Gate right after it. The chain above is the [planned plan](../types/run-plan.md#term-planned-plan) ([research-template.plan.json](research-template.plan.json), phase `planned`). The intent and requirement [nodes](../system/nodes.md#term-node) are the [prep plan](../types/run-plan.md#term-prep-plan) ([prep.plan.json](prep.plan.json), phase `prep`). Planned [steps](../system/nodes.md#term-step) read the accepted Brief as `prep.requirement.research_brief`.

## How a capability page is written

Every page follows one shape so coders and machines can find the same facts: **What it does; Where it sits (flow node, input, output); Declaration; Checks; Tests; Acceptance seeds** in that order, with other sections (Gate, How it works, Existing code it touches, RSI, Open) between them. Page types and required sections are in the [standard](../standards.md). Front matter: `id`, `type: capability`, `level: detail`, `provides` (its identity), `consumes` (type ids), `depends_on`. The Declaration is the contract. Pages do not copy type field tables.

Improvement hypotheses and benchmark [fixtures](../system/test-surfaces.md#term-fixture) per capability: [improvement guide](improvement.md), [benchmark material](benchmarking-material.md).
