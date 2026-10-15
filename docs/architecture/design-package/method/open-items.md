# Open items

`Tier 2 · Part of: [Method](README.md) · Serves: Standard`

These are the only items that stay open. Each needs a measurement or a fact from an owner in the real world. Every other question in the package has a ruling, recorded in the page that owns the fact and, where it differs from an owner design, in [owner rulings](../side-systems/owner-rulings.md).

| # | Item | Owner | What is needed | By when | Why it does not block the build |
|---|---|---|---|---|---|
| 1 | GB10 peak-memory measurement | Benchmark owner | Peak memory of the first pilot run (`purpose: feasibility`) on the server host, to confirm or lower the memory ceilings ([plan policy](../reference/run-plan.md#plan-policy), [pilot](../side-systems/benchmark-runner.md#october-30-pilot)) | The first pilot run | The plan policy ships with a ceiling of 32768 MB. The measurement may lower a value and never blocks code. |
| 2 | API provider endpoints and credentials | Routing owner | Real provider entries in the [shape defined](../side-systems/model-catalog.md#api-provider-entry): base URL, model IDs, credential env var name, timeout. The key values go in the protected env file | When model access is approved | M1 runs on the fixed Codex route. The router runs on mocked endpoints and every real provider stays disabled until then. |
| 3 | Named fixture custodian | RSI owner team | The name of one person for the [custodian role](../side-systems/rsi-workbench.md#hidden-fixture-custody) | Before the first RSI session with real hidden fixtures | The architect holds the role until then. The filesystem identity works the same for any holder. The workbench never blocks a run. |
| 4 | D32 product confirmation | Product owner | Confirmation that catching an unsupported citation at Tier 1 satisfies PRD 4.2.9 case 4 ([D32](decisions.md#d32)) | Before the October 30 acceptance | The design catches the fault and halts the run either way. A different ruling changes one case's tier wording, not the build. |

## Known limits

- Separate producer and verifier contexts do not guarantee independent errors. A schema and a readable view cannot prove scientific truth or real enforcement.
- This package proves no runtime behavior. Code, installed endpoint support, confinement and M1 completion need runtime evidence.
- The departures D5 and D6 from the PRD are recorded in [decisions](decisions.md#decisions-and-source-amendments).
