# Frozen M1 sources

Frozen on 2026-10-02 by Muk's direction. The [machine-readable manifest](source-freeze-2026-10-02.json) records exact bytes, hashes, repository locations and duplicate downloads. Dates and download suffixes do not determine authority.

## Authority and provenance

The [October 2 master PRD](prd-m1-full-2026-10-02.txt), SHA-256 `44928035205bdebae205d2b458bd438c2c6e0103e4eb2d834c6a93e1cfa37294`, defines M1 scope. Owner documents provide domain detail within that scope. Adopted architecture owns shared interfaces. Received files remain verbatim; architecture reconciliations live in the [decision ledger](../architecture/decisions.md).

| Input / owner | Selected version and role | Disposition |
|---|---|---|
| Master PRD / Ramika | October 2, 200082 bytes | frozen scope authority; Downloads `(1)` and `(2)` match |
| October 1 PRD / Ramika | 177840 bytes | historical; Downloads `PRD - Full.txt` and `(3)` match it |
| Model Routing / Xiaoyang | [v1.7](../architecture/model_router_design_en.md) | frozen owner input; both downloads match; canonical interface is the architecture adapter |
| RSI / Saurav | [full October 2](prd-m1-rsi-full.md) | frozen owner detail; `(1)` and `(2)` match; older full/short copies are historical |
| Data Foundation / Suraj | [PRD](prd-m1-data-foundation.md), [technical design](../architecture/data-foundation/capsule-run-records.md) | frozen owner detail; numbered downloads match |
| CC / Muk | [received full section](../architecture/prd/capsule-3w-full.md) | frozen source; current architecture supersedes proposed interface details while preserving whitelist limits |
| Benchmark / Saurav | [experiment v5](benchmark-experiment-design-v5-2026-10-02.md), [guide](benchmark-guide-2026-10-02.md) | external harness input; duplicate downloads match; schema pending at its export adapter |
| Verifier model-selection / proposer unnamed | [received proposal](verifier-model-selection-proposal-2026-10-02.md) | permitted isolated candidate analysis and unmodified-model integration; no training or production-route replacement |
| Coder / architecture consumer | [original seven questions](coder-architecture-requirements-2026-10-02.txt) | preserved input; [coding requirements](../architecture/system/coder-requirements.md) maps answers |
| Workflow/feature list/blank routing template | hashes and original filenames in manifest | historical unselected inputs; never override the full PRD |
| Earlier notes / Muk | `tundle/obby/HANDOFF.md` and `tundle/ai4research/notes/` outside this repository | navigation and historical rationale only; no architecture authority |

`historical_unselected_input` means a download is recorded, not imported as an active requirement. Existing copies and notes stay intact. The manifest also preserves hashes of earlier repository source checkpoints to keep their citations reproducible.

## Later arrivals

## Explicit deployment amendment, October 2

After the source freeze, Muk required Docker packaging, a monolith architecture and benchmark-runner endpoints in this session. Received sources and their hashes remain unchanged. This explicit agreement supersedes native-install/container-deferral deployment assumptions through [decision R10](../architecture/decisions.md) and [deployment](../architecture/system/deployment.md); it does not expand functional whitelist scope. This amendment is part of the architecture release provenance.

Add a received version beside the old one, preserve its bytes, and register a proposed source change with origin, hash, changed clauses, scope impact and affected contracts. It becomes active only through a new explicit source-freeze revision. Saurav's pending benchmark schema is integrated through a versioned export adapter; it does not reopen unrelated research modules.

Source verification compares every manifest hash against the current bytes. A mismatch blocks a handoff release until its provenance is resolved. The [architecture policies](../architecture/policies.md) govern contract revision, AI review and release packaging.
