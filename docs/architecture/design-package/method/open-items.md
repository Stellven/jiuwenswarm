# Open items

`Tier 2 · Part of: [Method](README.md) · Serves: Standard`

These are the only items that stay open. Each needs a measurement or a fact from an owner in the real world. Every other question in the package has a ruling, recorded in the page that owns the fact and, where it differs from an owner design, in [owner rulings](../side-systems/owner-rulings.md).

| # | Item | Owner | What is needed | By when | Why it does not block the build |
|---|---|---|---|---|---|
| 1 | Named fixture custodian | RSI owner team | The name of one person for the [custodian role](../side-systems/rsi-workbench.md#hidden-fixture-custody) | Before the first RSI session with real hidden fixtures | The architect holds the role until then. The filesystem identity works the same for any holder. The workbench never blocks a run. |
| 2 | D32 product confirmation | Product owner | Confirmation that catching an unsupported citation at Tier 1 satisfies PRD 4.2.9 case 4 ([D32](decisions.md#d32)) | Before implementation verification is finalized | The design catches the fault and halts the run either way. A different ruling changes one case's tier wording, not the build. |

## Known limits

- Hardware is settled, not open: the server host is a Linux GB10 with 128 GB of memory (256 GB if a second unit is added), well above every M1 ceiling. The first pilot run may still lower a ceiling, never raise the need.
- API provider endpoints and credentials are the routing owner's to define and add later. M1 needs none: it runs on the fixed Codex route, and the router runs on mocked endpoints until the owner adds real entries.
- Separate producer and verifier contexts do not guarantee independent errors. A schema and a readable view cannot prove scientific truth or real enforcement.
- This package proves no runtime behavior. Code, installed endpoint support, confinement and M1 completion need runtime evidence.
- The departures D5 and D6 from the PRD are recorded in [decisions](decisions.md#decisions-and-source-amendments).
