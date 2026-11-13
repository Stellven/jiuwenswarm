# 20261113 Satay CC Demo and Recovery v3 prepresentation

**Presenting:** open `20261113 Satay CC Demo Console prepresentation.html` in Chrome. It needs only a browser and this folder: no inference, network or factory. Press `N` for speaker notes and `1`–`6` to change views. The script is in `PRESENTATION.md`, and answers to likely questions are in `ATTACK QUESTIONS.md`.

**Continuing work on Satay:** run `bash scripts/start-codex.sh` from this extracted package. It starts a new interactive Codex session with `AUTONOMOUS.md` as context. It does not clone the previous chat, grant blanket permissions or start model work. Existing Codex authentication is reused and never bundled.

## What the demo shows

| Source | What it is | Status | Used for |
|---|---|---|---|
| J-OM13 | Historical 64-token matched experiment, fill plus predictive reads | Confirmed | The headline: 841.5 → 711.4 ms/token (−15.5% time, +18.3% throughput), four runs per headline arm |
| Fresh recording | Task `factory-e5b8d4b7`, 32-token fill-only | Inconclusive | Shows the CC-guided process and decision |
| Proof run (new in v3) | Task `factory-cc5e8585`: one plain-words `jiuwenswarm-factory ask` instruction, no web frontend | Accepted in 13 min; output identical to the frozen reference | Shows an agent integrating, building and screening through the CC runner. Operator fixed the scope. Not a speed claim |
| J-ASK1 (new in v3) | 1-round ABBA, plain vs the proof-run image, 32 tokens | Null (+7.6%, gate 23.4%) | Context only; never combined with J-OM13 |

The two are never treated as one run.

## Reading order

1. `PRESENTATION.md`: the timed script and evidence boundaries.
   - v3 adds `proof-ask-1/README.md`, with evidence in `evidence/proof-ask-1/` and `evidence/J-ASK1/`. The talk and console are unchanged from v2.
2. `context/engineering/ENGINEERING-DETAILS.md`: the two engineering details and their sources.
3. `ONTOLOGY.md`: the system ontology, engine slice, contract, work graph and CCs, and what the new slice link does.
4. `ATTACK QUESTIONS.md`: concise answers and limitations.
5. `HANDOFF.md`: exact state, commits, capsule versions, backups, model configuration and remaining actions.
6. `RECOVERY.md` and `context/recovery/`: restore, restart and checkpoint procedures.
7. `VALIDATION.md` and `REVIEW.md`: checks actually completed, and the independent review record.
8. `MODEL-CONFIG.md` and `BUDGET.md`: the effective agent model and the time/lab ledger.

## Package boundaries

**Historical records.** Everything in `context/historical/` and the original evidence is an immutable record. It may mention superseded instructions, older disk capacity or earlier claims, and it is not the current runbook.

**Sources.** The source bundles preserve exact pinned commits with `.shallow` boundary sidecars (see `SOURCE-PINS.json`). Keep each bundle with its sidecar.

**Not included:**
- model weights
- Docker base and engine images
- CUDA/JetPack
- Python environments
- authenticated agent runtimes

This is not a bare-metal disaster image.

**Versions.** Version 1 of this package, `20261113 Satay CC Demo and Recovery prepresentation.zip`, is preserved unchanged beside this v2 on internal backup storage and on the Danta drive.

**Storage.** Keep live Git workspaces and SQLite on internal storage. Danta holds only completed, checksum-verified archives.
