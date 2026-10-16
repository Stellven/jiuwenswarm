# Current product source receipt

The PRD body is supplied separately. This receipt identifies the product source adopted for the maintained design; it does not replace the PRD.

## Current source: received October 15, 2026

| Received filename | Bytes | SHA-256 |
|---|---:|---|
| PRD V.10 - M1 Acceptance Adjusted.txt | 270790 | `6d85972cdc8cf586a3d76b80d56510d695f03bfcf7838661afc7f71c35f4b3fc` |

Repository capture: `docs/product/received-prds/prd-m1-v10-2026-10-15.txt`. All 188 numbered clause headings match the October 13 index except §6.11, now titled "Implementation Stage 8 — Local-Isolated RSI Implementation". What changed: the PRD core M1 gate is Phase 1 Stages 0 to 7 only; Phase 2 is an implementation commitment with validation deferred; Phase 3 reports implementation, integration and verification as three separate statuses (unverified is never PASS); Dynamic Agent Planning is the targeted item that needs positive and negative path evidence; Model Routing is an implementation commitment with the Codex CLI route as the verified baseline; §6.14 is rewritten. [Decisions](../../method/decisions.md#d40) record the design response. D5 and D6 are unchanged.

[Clause allocation](../../method/clause-coverage.md) maps requirements.

## Historical receipts

| Earlier capture | Bytes | SHA-256 |
|---|---:|---|
| prd-m1-reviewed-2026-10-13.txt (received as `PRD - AI4Research (4).txt`, confirmed October 13) | 255245 | `890c63ee4849d61e8c7ddc980891985d57c59005ca6c62be45957c59e82782de` |
| prd-m1-current-2026-10-06.txt | 232489 | `6bd528778f0fd362eeff8bdbc76e60ae202fbe99cb879dd7fe24fd3b41762839` |
| prd-m1-current-2026-10-07.txt | 254883 | `10eaa9c6bd6e0c913422c2c8e5d501569c65f7bf839e0bd088c0da83ae4913dc` |

Earlier originals (the filenames above are repository names) remain under `docs/product/received-prds/`. Frozen experiment inputs retain their original PRDs and identities; they are not updated to this source. A supplied source must match the current receipt before its evidence is treated as current. The routing-owner standalone PRD is older background; the confirmed full PRD and adopted architecture determine present phase and binding boundaries.
