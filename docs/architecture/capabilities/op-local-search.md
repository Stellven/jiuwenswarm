---
id: cap.op-local-search
type: capability
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, ../capsule/runner.md]
provides: [op.local_search]
consumes: [cc.type.intake, cc.type.search_hits]
depends_on: [../types/search-hits.md, ../types/intake.md, ../capsule/runner.md]
tags: [m1, operator, capsule]
level: detail
prd: [3.3.2]
---

An operator capsule: one keyword query over the user's documents (PRD 3.3.2, "keyword queries against the local document buffer"). The pattern for every operator: a small `tool` that other capsules pin and call as a `nested` call, never a task node.

# `op.local_search`: one keyword query over the intake's documents

PRD: 3.3.2

> Answers: How does one keyword query score and return passages from the intake documents?

## What it does

It scores passages of the intake's documents by how many query words they contain, and returns the best documents with their best passages, verbatim. It is pure code: no model, no index, no network.

**Why not deepsearch's local search.** It needs a Milvus index and an embedding-model key, while PRD 3.3.2 asks only for keyword queries. Matching is a few lines of fixed code, specified exactly below, so every implementation gives the same answer.

## Where it sits

Nested in [search](search-capsule.md). Takes `query` and `documents`, gives `search_hits` ([search_hits](../types/search-hits.md)). Mechanical: no check of its own ([inventory](README.md)).

Schema: when a [work capsule](README.md#term-work-capsule) calls it through the runner broker, the call is `tools-v1.schema.json#broker_search_request` and the reply `tools-v1.schema.json#broker_search_result` (`service: local`).

## Declaration (`capsule.json`)

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "op.local_search",
    "kind": "tool",
    "carrier": {"ref": "local_search.py:search", "sha256": "<author kit>"},
    "summary": "Run one keyword query over the given documents and return the best-matching documents with their best passages, verbatim, at most top_k documents."
  },
  "ports": {
    "inputs": [
      {"name": "query", "type": "text", "required": true, "description": "One keyword query."},
      {"name": "top_k", "type": "integer", "required": true, "description": "The most documents to return, 1 to 5."},
      {"name": "intake", "type": "intake", "required": true, "description": "The run's intake; its documents are searched."}
    ],
    "outputs": [
      {"name": "hits", "type": "search_hits", "check_id": "local_chunks_verbatim", "description": "The matching documents, best first."}
    ]
  },
  "needs": {
    "when": [
      {"id": "top_k_at_least_1", "path": "inputs.top_k", "op": "gte", "value": 1},
      {"id": "top_k_at_most_5", "path": "inputs.top_k", "op": "lte", "value": 5}
    ],
    "external": [], "network": "none", "human_interaction": "none", "resources": {"timeout_s": 30}
  },
  "changes": {"effect_class": "pure", "effects": [], "state_kind": "none"},
  "guarantees": {"checks": [
    {"id": "local_chunks_verbatim", "anchor": "deterministic", "target": "ports.outputs.hits",
     "over": "inputs_and_outputs", "applies_at": "both",
     "runner": {"ref": "checks/local_checks.py:local_chunks_verbatim", "sha256": "<author kit>"},
     "description": "There are at most top_k hits, all of kind local; each source_id is an intake document_id, and each chunk appears verbatim in that document's text.",
     "author": "cc-team"},
    {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.hits",
     "over": "inputs_and_outputs", "applies_at": "admission",
     "runner": {"ref": "checks/local_checks.py:matches_reference", "sha256": "<author kit>"},
     "description": "On a test case, the hits equal the expected ones exactly, in order.",
     "author": "cc-team"}
  ]},
  "evolution": {"rsi": "none"}
}
```

## The algorithm, exactly

1. **Words:** the distinct members of `re.findall(r"\w+", query.casefold())`. No words gives no hits.
2. **Passages:** for each document, `re.split(r"\n\s*\n", text)`, each `.strip()`ped, with empty ones dropped. A passage over 1,200 characters is cut into consecutive 1,200-character slices.
3. **Score:** a passage's score is the number of query words in `set(re.findall(r"\w+", passage.casefold()))`. Passages that score 0 are dropped.
4. **Per document:** keep its top 3 passages by (score descending, position ascending), then list them in document order. The document's score is its best passage's score.
5. **Rank** documents by (score descending, position in `intake.documents` ascending), and keep the first `top_k`.
6. **Hit:** `source_id` is the `document_id`, `kind` is `local`, `title` and `locator` are the document's `path`, `authors` is `[]`, and `chunks` are the kept passages.

## Checks

The [checks](../capsule/fields.md#term-check) are the `checks` array in the [Declaration](../capsule/fields.md#term-declaration) above.

## Tests (runs and replay)

Admission replay uses two cases over a two-document intake with an exact expected answer, covering the declared checks. At runtime the [Gate host](../capsule/gate-host.md#term-gate-host) persists the nested call's mechanical [Verification](../schemas/verification-record.md#term-verification) before returning its output to the parent; an empty semantic criteria set is recorded as [Tier 2](../verification.md#term-tier-2) `NOT_RUN`. The parent's independent semantic [Gate](../verification.md#term-gate) includes that nested evidence. [Runner](../capsule/runner-broker.md#nested-calls-and-the-broker) defines this protocol.

## Existing code it touches

None.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.op-local-search.AC-01 | PRD 3.3.2 | The two-document admission case returns exactly the expected hits in order (matches_reference). | BLOCK |
| cap.op-local-search.AC-02 | PRD 3.3.2 | At most top_k hits are returned, all of [kind](../capsule/capsule.md#term-capsule-kind) local, each source_id is an intake document_id and each chunk appears verbatim in that document. | BLOCK |
| cap.op-local-search.AC-03 | PRD 3.3.2 | A query with no words gives no hits; passages over 1,200 characters are cut into 1,200-character slices; at most 3 passages per document. | BLOCK |
| cap.op-local-search.AC-04 | N_node | top_k outside [1,5] is refused by the needs predicate before the call. | BLOCK |
| cap.op-local-search.AC-05 | N_node | The [operator](README.md#term-operator) makes no model, index or network call. | BLOCK |
