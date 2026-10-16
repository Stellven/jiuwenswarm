# Open items

`Tier 2 · Part of: [Method](README.md) · Serves: Standard`

**No design item is open.** Every question has a ruling, recorded in the page that owns the fact and, for component integration, in [owner rulings](../side-systems/owner-rulings.md).

## Gaps found while building

The package is not complete down to every line of code, and M1 is not expected to be built in one pass. The build window includes time to fix what the first build gets wrong. When a builder meets a gap:
- Fill it with the smallest choice that fits the [principles](principles.md) and the contracts around it. Accuracy first: never pass bad output forward.
- Never weaken a check, a gate or an authority boundary to fill a gap.
- Record the choice where reviewers will see it (the change description). If the choice adds or changes a field, check or enum, update the tier 3 page that owns it in the same change.

## Settled by default

These were open and are now closed by a default. An owner may change a default later; none blocks the build.

| Item | Default | Who may change it |
|---|---|---|
| Server hardware | A Linux GB10 server with 128 GB of memory (256 GB if a second unit is added), well above every M1 ceiling. The first pilot run may lower a ceiling | Benchmark owner |
| API provider endpoints and credentials | None in M1. M1 runs on the fixed Codex route. The router runs on mocked endpoints until the routing owner adds real entries in the [shape defined](../side-systems/model-catalog.md#api-provider-entry) | Routing owner |
| Fixture custodian | The architect holds the [custodian role](../side-systems/rsi-workbench.md#hidden-fixture-custody) until the RSI owner team names one person. It matters only once RSI runs with real hidden fixtures | RSI owner team |
| PRD 4.2.9 case 4 (unsupported citation) | Adopted as [D32](decisions.md#d32): deterministic host checks catch it before the verifier runs, and the node stops | Product owner. An objection would add a verifier criterion, not remove the check |

## Known limits

- Separate producer and verifier contexts do not guarantee independent errors. A schema and a readable view cannot prove scientific truth or real enforcement.
- This package proves no runtime behavior. Code, installed endpoint support, confinement and M1 completion need runtime evidence.
- The departures D5 and D6 from the PRD are recorded in [decisions](decisions.md#decisions-and-source-amendments).
