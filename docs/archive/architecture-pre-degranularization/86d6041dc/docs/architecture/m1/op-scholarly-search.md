---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, ../system/integration.md, ../capsule/runner.md]
provides: [op.scholarly_search]
consumes: [cc.type.search_hits, system.adapters]
depends_on: [../types/search-hits.md, ../system/integration.md, ../capsule/runner.md]
tags: [m1, operator, capsule]
---

> **Draft: reopened for changed shared contracts.** An operator capsule: one keyword query against arXiv and Semantic Scholar, through deepsearch's connectors (PRD 3.3.2, "bounded, structured external queries against designated academic APIs ... using deepsearch's built-in connectors").

# `op.scholarly_search`: one query against the academic literature

## What it does

It asks arXiv and Semantic Scholar for one query, keeps at most `top_k` papers in total, and returns each with its abstract as its passage. Everything about the services is in `cc.adapters.deepsearch` ([integration](../system/integration.md#deepsearch-scholarly-search)): how it calls them, its timeouts, its spacing, its errors and its replay.

**Why deepsearch's connectors, not its agent.** The `DeepSearchAgent` needs its own model API key (M1's model is the Codex runtime only), and it would hide model behaviour inside an operator. The connectors need no model.

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
     "author": "muk"},
    {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.hits",
     "over": "inputs_and_outputs", "applies_at": "admission",
     "runner": {"ref": "checks/scholarly_checks.py:matches_reference", "sha256": "<author kit>"},
     "description": "On a test case, the hits' source_ids equal the expected ones, in order.",
     "author": "muk"}
  ]},
  "evolution": {"rsi": "none"}
}
```

**Why these choices:**
- **`read_only`, `reads_external`:** it changes nothing and reads public services, so it may run unattended. Rule `state_fixtures_present` makes its tests carry fixtures, which is how replay works.
- **`network: egress`** authorizes only the designated academic connector route under the validated runtime profile. The operator cannot obtain model credentials or arbitrary host/network access; [environment](../system/environment.md) owns enforcement and fail-closed startup probes.
- **`timeout_s: 120`:** one request per service, each capped at 50 s by the adapter, plus the spacing wait.

## How it works

1. `rows = await cc.adapters.deepsearch.scholarly(query, top_k)`: at most `top_k` rows, merged and de-duplicated by the adapter.
2. Each row becomes a hit: `source_id` (`arxiv:<id without version>` or `s2:<paperId>`), `kind`, `title`, `authors`, `published`, `locator` (the row's `url`) and `chunks: [content]`.
3. **One service down,** the other answering: the hits come from the one that answered, plus `cc.issue("hits", "EXTERNAL_UNAVAILABLE", "<service> did not answer")`. **Both down:** `cc.ExternalUnavailable` ([runner](../capsule/runner.md#tool-a-python-function-in-its-own-process)).

## Runs, and tests

Admission cases cover the declared checks and carry recorded service responses that the adapter replays ([integration](../system/integration.md#deepsearch-scholarly-search)). At runtime the Gate host persists the nested call's mechanical Verification before returning its output to the parent; an empty semantic criteria set is Tier 2 `NOT_RUN`. The parent retains partial-service limitations and includes the nested evidence in its semantic Gate. [Runner](../capsule/runner.md#nested-calls-and-the-broker) owns this protocol.

## Existing code it touches

`cc.adapters.deepsearch` only.
