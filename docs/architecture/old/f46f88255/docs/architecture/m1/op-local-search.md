---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, ../capsule/runner.md]
provides: [op.local_search]
consumes: [cc.type.intake, cc.type.search_hits]
depends_on: [../types/search-hits.md, ../types/intake.md, ../capsule/runner.md]
tags: [m1, operator, capsule]
---

> **Draft: reopened for changed shared contracts.** An operator capsule: one keyword query over the user's documents (PRD 3.3.2, "keyword queries against the local document buffer"). The pattern for every operator: a small `tool` that other capsules pin and call as a `nested` call, never a run step.

# `op.local_search`: one keyword query over the intake's documents

## What it does

It scores passages of the intake's documents by how many query words they contain, and returns the best documents with their best passages, verbatim. It is pure code: no model, no index, no network.

**Why not deepsearch's local search.** It needs a Milvus index and an embedding-model key, while PRD 3.3.2 asks only for keyword queries. Matching is a few lines of fixed code, specified exactly below, so every implementation gives the same answer.

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
     "author": "muk"},
    {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.hits",
     "over": "inputs_and_outputs", "applies_at": "admission",
     "runner": {"ref": "checks/local_checks.py:matches_reference", "sha256": "<author kit>"},
     "description": "On a test case, the hits equal the expected ones exactly, in order.",
     "author": "muk"}
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

## Runs, and tests

Admission replay uses two cases over a two-document intake with an exact expected answer, covering the declared checks. At runtime the Gate host persists the nested call's mechanical Verification before returning its output to the parent; an empty semantic criteria set is recorded as Tier 2 `NOT_RUN`. The parent's independent semantic Gate includes that nested evidence. [Runner](../capsule/runner.md#nested-calls-and-the-broker) owns this protocol.

## Existing code it touches

None.
