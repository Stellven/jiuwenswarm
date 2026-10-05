---
id: cap.op-codesearch
type: capability
status: draft
version: 2
sources: [../../product/prd-m1-full-2026-10-02.txt, ../system/integration.md]
provides: [op.codesearch]
consumes: [cc.type.code_hits]
depends_on: [../types/code-hits.md, ../system/storage.md, ../system/environment.md]
tags: [m1, operator]
level: detail
prd: [3.5.3]
---

# `op.codesearch`: locate the intervention

PRD: 3.5.3

> Answers: How does the CodeSearch operator find the code location of an intervention in the authorized repository snapshot?

## What it does

Finds the code location of the intervention in the authorized repository [snapshot](../capsule/library.md#term-library-snapshot) and returns verbatim line spans as `code_hits`.

## Where it sits

Nested in Hypothesis and POC ([inventory](README.md)). Takes `query` and `repository` (an authorized snapshot), gives `hits` ([code_hits](../types/code-hits.md)). Mechanical: no check of its own.

A nested tool under `capsules/op.codesearch/` with adapter `cc/adapters/codesearch.py`. Required inputs query:text, repository:path and top_k:integer in [1,5]; required output hits:[code_hits](../types/code-hits.md#term-code-hits). It is [idempotent](../contracts/principles.md#term-idempotency), writes only `fs:workspace/.cc/codesearch/*`, and has no network/model/human access.

Repository must be the authorized project_asset snapshot identified by the blueprint/snapshot request; it is not an arbitrary host directory or reference document. Index by snapshot content hash plus adapter/index version. Repeated identical index requests reuse committed indexes. Unreadable/absent resource fails with STORE_NOT_FOUND or INPUT_INCOMPLETE; unsupported language yields an empty hit list and an explicit limitation, never fabricated code.

Source checked in openjiuwen-deepsearch commit `ff243bca4ab409116476587dcb106cf526581804`: `codesearch/openjiuwen_codesearch/retropus/retrievers/bm25.py:294` BM25Retriever, `:381` build_index, `:445` search_ast_nodes. Borrow syntax-aware Python chunking and this model-free BM25 retrieval through the local adapter; do not import the upstream package dependency tree. Do not instantiate the agentic retriever or supply independent model keys. Adapter builds equivalent local file/AST node input from the approved snapshot, maps the returned structured hits to the canonical type and rereads each selected line range to ensure verbatim source bytes. Results are ordered by retrieval relevance with path/start_line/end_line as deterministic tie keys; preserve this ranking/chunking interface while implementing it with pinned compatible local dependencies.

[code_hits](../types/code-hits.md) defines the result schema. The adapter uses the repository-compatible pinned package set; upstream retrieval behavior is a precedent, not a runtime [dependency requirement](../types/dependency-requirement.md#term-dependency-requirement). Import/chunking [fixtures](../system/test-surfaces.md#term-fixture) remain implementation validation. Source presence does not claim a tested import. [Environment](../system/environment.md) is the home of startup dependencies and confinement; [runner](../capsule/runner.md) is the home of timeouts/cancellation and exact duplicate identities. No auto-download/clone or package installation occurs in a run. Empty hits cause Hypothesis/POC to record an unresolved intervention and halt if an exact required mechanism location cannot be established.

Schema: when a [work capsule](README.md#term-work-capsule) calls it through the runner broker, the call is `tools-v1.schema.json#broker_search_request` and the reply `tools-v1.schema.json#broker_search_result` (`service: code`).

## Declaration

No [Declaration](../capsule/fields.md#term-declaration) JSON is abridged on this page. The paragraph above states [ports](../capsule/fields.md#term-port), [effect class](../capsule/fields.md#term-effect-class) and permissions; the Declaration format is in [capsule fields](../capsule/fields.md).

## Checks

No Checks beyond the type guarantees of [code_hits](../types/code-hits.md) and the independent [checks](../capsule/fields.md#term-check) in Tests below.

## Tests

Independent checks verify sorted bounds, source line equality, immutable snapshot scope, no model call and typed unavailable/missing input outcomes. Runtime results are left to the coding role.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.op-codesearch.AC-01 | PRD 3.5.3 | top_k outside [1,5] is refused; hits are sorted and bounded by top_k. | BLOCK |
| cap.op-codesearch.AC-02 | PRD 3.5.3 | Each returned hit line range rereads equal to the snapshot [source text](../types/source-text.md#term-source-text). | BLOCK |
| cap.op-codesearch.AC-03 | N_node | The repository input must be the authorized project_asset snapshot; an arbitrary host path is refused. | BOUNDARY |
| cap.op-codesearch.AC-04 | N_node | An unsupported language returns an empty hit list plus an explicit limitation, never fabricated code. | BLOCK |
| cap.op-codesearch.AC-05 | N_node | An unreadable or absent resource fails with STORE_NOT_FOUND or INPUT_INCOMPLETE; no model call, network or package install occurs. | BOUNDARY |
| cap.op-codesearch.AC-06 | N_node | Repeating an identical index request reuses the committed index. | BLOCK |
