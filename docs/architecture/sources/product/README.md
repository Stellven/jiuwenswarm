# Sources required for specification

**Current product input:** [latest received PRD](prd-m1-current-2026-10-06.txt), received October 6; 232,081 bytes, SHA256 `897af8427e2cf4e2427a2097b9b9e8a5a427a7de53b89f4e541d2cc437594036`. It is preserved verbatim; the receipt date is not an inferred author revision. Architecture [decisions](../../principles.md#decisions-and-source-amendments) record explicit amendments and [phase/stage accounting](../../delivery-phases.md) resolves inconsistent source labels.

| Required input | Purpose |
|---|---|
| [Current master PRD](prd-m1-current-2026-10-06.txt) | Product scope, authority, stages and completion criteria |
| [Data Foundation](prd-m1-data-foundation.md) | Evidence, record and export semantics; master PRD and D6/D9 govern conflicts |
| [RSI owner source](prd-m1-rsi-full.md) | Bounded mutation, fixture custody, query budgets and calibration requirements within master scope |
| [Report format source](report-writer-upstream-2026-10-01.md) | Delivery format input, with no authorization to publish |
| [CC semantic description](../capsule-semantic-v2.10b.md), [schema](../capsule.schema.json), [M1 policy](../policy-m1.json) | Authored capability contract and profile source; reconcile format differences through the [field inventory](../../capsule/declaration.md) before implementation |

These retained source files are unchanged. Earlier PRDs, discussion archives, benchmark proposals and copies of existing coding records are excluded from this handoff. See [coding authorities](../../authority-index.md) for repository-local process and task links.
