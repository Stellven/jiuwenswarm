# Sources and design authority

**Reading level: AI reference.** Start with [README](README.md). The current PRD owns product requirements; adopted design decisions own technical realization and explicitly authorized local departures. Source snapshots are evidence, not competing current schemas.

| Input | Current use |
|---|---|
| [Latest PRD and receipt identity](sources/product/README.md) | October 13, 2026 confirmed source identity; PRD supplied separately, prior receipts retained |
| [Principles/decisions](principles.md#decisions-and-source-amendments) | Current architectural choices; D5 is current-source aligned; D6 remains the recorded packaging exception; D19 records the authorized current-core planner amendment |
| [Critical contracts and field references](reference/README.md) | Current shared representation and consumer obligations |
| [Historical CC semantic description](sources/capsule-semantic-v2.10b.md), [machine schema](sources/capsule.schema.json), [profile](sources/policy-m1.json) | Immutable provenance; original shapes/maturity labels are reconciled in the current [CC reference](capsule/declaration.md) |
| [Core build](core-build.md) | Current bounded assignment; its planner promotion is D19 and RSI is an independent optional target |
| [Clause coverage](coverage-allocation.md) and [design review](coverage.md) | Full-M1 product responsibility mapping and design-level checks; mappings do not claim runtime acceptance or current-core assignment |
| [Pinned history](history.md) | Optional provenance; routine implementation needs no history search |

The PRD owns overall requirements and required outcomes. Design interprets the PRD and owns architecture and implementation-facing details that achieve those outcomes. If implementation guidance conflicts, follow the current design. Product obligations remain binding; a conflict that changes an obligation needs an explicitly recorded authorized decision.

One current contract governs each public boundary. Human prose explains meaning; schemas define selected exact fields; examples illustrate them and grant no runtime authority. Transport/internal classes do not change shared semantics. Development registration and evidence procedures remain outside this architecture package.

## Current semantic-review scope

[D20](principles.md#d20-declarationoutput-only-semantic-review) limits semantic input to declaration/output; earlier full-context descriptions remain source context. Host checks retain runtime evidence. [D21](decision-review.md#d21) governs November generation/admission and December composition.
