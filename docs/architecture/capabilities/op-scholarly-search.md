---
id: cap.op-scholarly-search
type: capability
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, ../system/integration.md, ../capsule/runner.md]
provides: [op.scholarly_search]
consumes: [cc.type.search_hits, system.adapters]
depends_on: [../types/search-hits.md, ../system/integration.md, ../capsule/runner.md]
tags: [m1, operator, capsule]
level: detail
prd: [3.3.2]
---

An operator capsule: one keyword query against arXiv and Semantic Scholar, through deepsearch's connectors (PRD 3.3.2, "bounded, structured external queries against designated academic APIs ... using deepsearch's built-in connectors").

# `op.scholarly_search`: one query against the academic literature

PRD: 3.3.2

> Answers: How does one query go to arXiv and Semantic Scholar and come back as search hits?

## What it does

It asks arXiv and Semantic Scholar for one query, keeps at most `top_k` papers in total, and returns each with its abstract as its passage. Everything about the services is in `cc.adapters.deepsearch` ([integration](../system/integration.md#deepsearch-scholarly-search)): how it calls them, its timeouts, its spacing, its errors and its replay.

**Why deepsearch's connectors, not its agent.** The `DeepSearchAgent` needs its own model API key (M1's model is the Codex runtime only), and it would hide model behaviour inside an [operator](README.md#term-operator). The connectors need no model.

## Where it sits

Nested in [search](search-capsule.md). The [Declaration](../capsule/fields.md#term-declaration) says `network: egress`, but the child [runs](../system/lifecycle.md#term-run) with no network and the egress is brokered ([permissions](../capsule/permissions.md#how-a-declaration-becomes-rules)). Takes `query`, gives `search_hits` ([search_hits](../types/search-hits.md)). Mechanical: no check of its own ([inventory](README.md)).

Schema: when a [work capsule](README.md#term-work-capsule) calls it through the runner broker, the call is `tools-v1.schema.json#broker_search_request` and the reply `tools-v1.schema.json#broker_search_result` (`service: scholarly`).

## Declaration (`capsule.json`)

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "op.scholarly_search",
    "kind": "tool",
    "carrier": {"ref": "scholarly_search.py:search", "sha256": "<author kit>"},
    "summary": "Run one keyword query against arXiv and Semantic Scholar and return at most top_k papers, each with its abstract as the matching passage."
  },
  "ports": {
    "inputs": [
      {"name": "query", "type": "text", "required": true, "description": "One keyword query."},
      {"name": "top_k", "type": "integer", "required": true, "description": "The most papers to return, 1 to 5."}
    ],
    "outputs": [
      {"name": "hits", "type": "search_hits", "check_id": "within_top_k", "description": "The papers, best first."}
    ]
  },
  "needs": {
    "when": [
      {"id": "top_k_at_least_1", "path": "inputs.top_k", "op": "gte", "value": 1},
      {"id": "top_k_at_most_5", "path": "inputs.top_k", "op": "lte", "value": 5}
    ],
    "external": [], "network": "egress", "human_interaction": "none", "resources": {"timeout_s": 120}
  },
  "changes": {"effect_class": "read_only", "effects": [], "state_kind": "reads_external"},
  "guarantees": {"checks": [
    {"id": "within_top_k", "anchor": "deterministic", "target": "ports.outputs.hits",
     "over": "inputs_and_outputs", "applies_at": "both",
     "runner": {"ref": "checks/scholarly_checks.py:within_top_k", "sha256": "<author kit>"},
     "description": "There are at most top_k hits, each of kind arxiv or semantic_scholar, with an http or https locator.",
     "author": "cc-team"},
    {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.hits",
     "over": "inputs_and_outputs", "applies_at": "admission",
     "runner": {"ref": "checks/scholarly_checks.py:matches_reference", "sha256": "<author kit>"},
     "description": "On a test case, the hits' source_ids equal the expected ones, in order.",
     "author": "cc-team"}
  ]},
  "evolution": {"rsi": "none"}
}
```

**Why these choices:**
- **`read_only`, `reads_external`:** it changes nothing and reads public services, so it may run unattended. Rule `state_fixtures_present` makes its tests carry [fixtures](../system/test-surfaces.md#term-fixture), which is how replay works.
- **`network: egress`** declares that the operator needs outside reach, and nothing more. The [restricted child](../capsule/process-boundary.md#term-restricted-child) has no network at all: the request leaves the child over its broker channel and the broker, not the child, reaches only the designated academic connectors under the validated runtime profile. The operator cannot obtain model credentials or arbitrary host/network access; [environment](../system/environment.md) is the home of enforcement and fail-closed startup [probes](../system/environment.md#term-probe).
- **`timeout_s: 120`:** one request per service, each capped at 50 s by the adapter, plus the spacing wait.

## How it works

1. `rows = await cc.adapters.deepsearch.scholarly(query, top_k)`: at most `top_k` rows, merged and de-duplicated by the adapter.
2. Each row becomes a hit: `source_id` (`arxiv:<id without version>` or `s2:<paperId>`), `kind`, `title`, `authors`, `published`, `locator` (the row's `url`) and `chunks: [content]`.
3. **One service down,** the other answering: the hits come from the one that answered, plus `cc.issue("hits", "EXTERNAL_UNAVAILABLE", "<service> did not answer")`. **Both down:** `cc.ExternalUnavailable` ([runner](../capsule/runner-handlers.md#tool-a-python-function-in-its-own-process)).

## Checks

The [checks](../capsule/fields.md#term-check) are the `checks` array in the Declaration above.

## Tests (runs and replay)

Admission cases cover the declared checks and carry recorded service responses that the adapter replays ([integration](../system/integration.md#deepsearch-scholarly-search)). At runtime the [Gate host](../capsule/gate-host.md#term-gate-host) persists the nested call's mechanical [Verification](../schemas/verification-record.md#term-verification) before returning its output to the parent; an empty semantic criteria set is [Tier 2](../verification.md#term-tier-2) `NOT_RUN`. The parent retains partial-service limitations and includes the nested evidence in its semantic [Gate](../verification.md#term-gate). [Runner](../capsule/runner-broker.md#nested-calls-and-the-broker) defines this protocol.

## Existing code it touches

`cc.adapters.deepsearch` only.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.op-scholarly-search.AC-01 | PRD 3.3.2 | At most top_k hits, each of [kind](../capsule/capsule.md#term-capsule-kind) arxiv or semantic_scholar with an http or https locator (within_top_k). | BLOCK |
| cap.op-scholarly-search.AC-02 | PRD 3.3.2 | On recorded service replays, source_ids equal the expected ones in order (matches_reference). | BLOCK |
| cap.op-scholarly-search.AC-03 | N_node | One service down and the other answering returns hits from the answering one plus an EXTERNAL_UNAVAILABLE issue. | BOUNDARY |
| cap.op-scholarly-search.AC-04 | N_node | Both services down raises ExternalUnavailable. | BOUNDARY |
| cap.op-scholarly-search.AC-05 | US-11 | The child has no network of its own; the operator cannot reach model credentials or hosts other than the designated academic connectors; a probe to another host is denied. | SYSTEM |
| cap.op-scholarly-search.AC-06 | N_node | The call completes within the declared 120 s timeout; the adapter caps each service request at 50 s. | BOUNDARY |
