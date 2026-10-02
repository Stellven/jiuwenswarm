---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../system/integration.md]
provides: [op.codesearch]
consumes: [cc.type.code_hits]
depends_on: [../types/code-hits.md, ../system/storage.md, ../system/environment.md]
tags: [m1, operator]
---

# `op.codesearch`: locate the intervention

A nested tool under `capsules/op.codesearch/` with adapter `cc/adapters/codesearch.py`. Required inputs query:text, repository:path and top_k:integer in [1,5]; required output hits:code_hits. It is idempotent, writes only `fs:workspace/.cc/codesearch/*`, and has no network/model/human access.

Repository must be the authorized project_asset snapshot identified by the blueprint/snapshot request; it is not an arbitrary host directory or reference document. Index by snapshot content hash plus adapter/index version. Repeated identical index requests reuse committed indexes. Unreadable/absent resource fails with STORE_NOT_FOUND or INPUT_INCOMPLETE; unsupported language yields an empty hit list and an explicit limitation, never fabricated code.

Source checked in openjiuwen-deepsearch commit `ff243bca4ab409116476587dcb106cf526581804`: `codesearch/openjiuwen_codesearch/retropus/retrievers/bm25.py:294` BM25Retriever, `:381` build_index, `:445` search_ast_nodes. Use syntax-aware Python chunking and this model-free retrieval. Do not instantiate the agentic retriever or supply independent model keys. Adapter builds the upstream file/AST node input from the approved snapshot, maps the returned structured hits to the canonical type and rereads each selected line range to ensure verbatim source bytes. Results are ordered by retrieval relevance with path/start_line/end_line as deterministic tie keys; choose no internal search algorithm beyond the existing wrapper.

[code_hits](../types/code-hits.md) owns the result schema. The dependency/import compatibility check is still issue 33; the approved adapter must resolve its package choice before enabling the operator. Source presence does not claim a tested import. [Environment](../system/environment.md) owns startup dependencies and confinement; [runner](../capsule/runner.md) owns timeouts/cancellation and exact duplicate identities. No auto-download/clone or package installation occurs in a run. Empty hits cause Hypothesis/POC to record an unresolved intervention and halt if an exact required mechanism location cannot be established.

Independent checks verify sorted bounds, source line equality, immutable snapshot scope, no model call and typed unavailable/missing input outcomes. Runtime results are left to the coding role.
