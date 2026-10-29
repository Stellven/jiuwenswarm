# Design package delivery: Capsule and model-routing integration

This receipt pins the October 13 full M1 [design package](../../design-package/README.md) and matched [compact package](../../design-package-compact/README.md), with the current PRD (4) and the model-routing owner’s design integrated at a shared Capsule boundary. It records documentation identity and consistency checks; it does not establish implementation, runtime acceptance, model quality, or human approval.

The current PRD (4) is supplied separately as [the received product source](../../../product/received-prds/prd-m1-reviewed-2026-10-13.txt). The original routing-owner bytes are retained under the full package’s source receipt. The route algorithm/catalog and provider behavior remain owned in the separate `model-routing/` component. The shared integration reference owns the protected export, profile boundary, frozen decision handoff, dispatch recheck, and provenance. Phase 1 remains the fixed Codex baseline; API-only router integration remains Phase 3.

| Reading measurement | Full | Compact |
|---|---:|---:|
| Same 22 explanatory documents, including Mermaid text | 28,290 words | 17,606 words |
| Three-document orientation (`README.md`, `m1-design.md`, `principles.md`) | 5,120 words | 2,929 words |
| Intention Compiler Main/Context entrypoints | 1,523 words | 1,523 words |
| Package files | 281 | 239 |
| Byte-identical shared files | 213 | 213 |

The compact explanatory reduction is **37.77%** over the named 22 documents. Word counts use whitespace-separated tokens and include Mermaid text; they do not estimate coding time, model quality, or total input tokens. `comparison.json` records every package file hash, shared-byte path, measurement, source identity, and schema comparison. Eight pre-existing machine schema files remain byte-identical to base commit `5f4e23fd3e56af4971f886a2b4dd049b9c15d0fe` and to their paired full/compact copies.

Run `python validate.py` from this directory in a clean checkout, or pass the full and compact package roots as arguments. It verifies exact inventories and readings, current PRD/router source hashes, unchanged existing schemas, shared bytes, and both independent portable package validators.

The full validator reports 7 critical schemas plus common definitions, 107 indexed examples/context records, 74 negative cases, 188 PRD headings, 42 named field contracts, and 32 diagram source/projection hash sets. The compact validator reports the same contracts, examples, headings, and negative cases, with 11 diagram source/projection hash sets. A separate five-case corrupted-copy check rejects missing/escaping views, field-type drift, stale pins, and a missing required export field. These checks establish documentation and synthetic-fixture consistency only. They do not exercise an authenticated exporter, live admission or dispatch, route selection, provider calls, runtime atomicity, or budget enforcement.

The earlier [October 13 pre-routing delivery](../design-package-delivery-2026-10-13/README.md) retains its original files, counts, and results. This receipt does not rewrite that frozen record. A separate Capsule closeout dossier remains in the Git-ignored architecture notes area and is not part of this package delivery.
