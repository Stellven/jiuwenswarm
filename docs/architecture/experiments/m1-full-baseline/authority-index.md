# Sources and design authority

**Reading level: AI reference.** Start with [README](README.md). The current PRD owns product requirements; adopted design decisions own technical realization and explicitly authorized local departures. Source snapshots are evidence, not competing current schemas.

| Input | Current use |
|---|---|
| [Latest PRD and receipt identity](sources/product/README.md) | Verbatim October 7 download; prior receipt retained |
| [Principles/decisions](principles.md#decisions-and-source-amendments) | Current architectural choices; D5/D6 exceptions remain explicit |
| [Critical contracts and field references](reference/README.md) | Current shared representation and consumer obligations |
| [Historical CC semantic description](sources/capsule-semantic-v2.10b.md), [machine schema](sources/capsule.schema.json), [profile](sources/policy-m1.json) | Immutable provenance; original shapes/maturity labels are reconciled in the current [CC reference](capsule/declaration.md) |
| [Clause coverage](coverage-allocation.md) and [design review](coverage.md) | Architectural responsibility/phase mapping and design-level checks |
| [Pinned history](history.md) | Optional provenance; routine implementation needs no history search |

One current contract governs each public boundary. Human prose explains meaning; schemas define selected exact fields; examples illustrate them and grant no runtime authority. Transport/internal classes do not change shared semantics. Development registration and evidence procedures remain outside this architecture package.
