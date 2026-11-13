# Result and evidence index

Headline = decode ms/token (tokens/s alongside), plain vs engine, matched conditions; output agreement and engagement shown; startup/prefill not included.

## This recording — fresh candidate, **PRELIMINARY (not a confirmed keep)**
Contract `qwen36-quick-v1` (32 tokens; own reference `cad62aa9`, frozen on the plain image). Component: **demand fill only** (mmap_advice + router_prefetch are dormant source prerequisites; one change active). Task `factory-e5b8d4b7…`, branch `demo-incremental-4` in the owned llama.cpp checkout.

| Check | plain ms/tok (tok/s) | fill ms/tok (tok/s) | gate | output |
|---|---|---|---|---|
| Screen (1 lab run) | — | 972.59 (1.03) | not a comparison | identical |
| ABBA 1 round | 903.98 (1.11) | 839.69 (1.19) | null: +7.66% < threshold 7.83% (A/A 3.9%) | identical |
| ABBA 3 rounds (operator-authorised confirmation) | 956.92 (1.05) | 854.44 (1.17) | null: +11.99% < threshold 25.65% (A/A noise 12.8%) | identical |

Both ABBAs favour fill; neither clears the noise gate, so it is **not** confirmed. Engagement: fill counters show activity (6.27 GB read, 1,240 decode fills); both ABBAs' candidate runs pass all 3 switch regexes. The screen's two contract-level checks (effective-config line, thread names) are 0/2 because the fill-only build lacks patches 08/09 logging — a reporting gap, not evidence of inactivity. Predictive reads (expert_pregate) were deferred (budget). Image `factory/llamacpp:incremental4-fill` = `sha256:405eb5e7…e0d43`, built once (165 s) from `00c6038f1` (clean tree `d63f6127`). Plain = `factory/llamacpp:bare-cf34d311` (`sha256:a9a0c71c…`), imported from `operator-bare-build:346fe01b`, not rebuilt.

## Recorded evidence (64-token contract — different workload, never combined)
- **J-OM13 — confirmed (gate improved):** plain 841.5 ms/token (1.19 tok/s) → fill + predictive reads image `bd173c08-restored-0b514fba` 711.4 (1.41), 12 runs, ratio 1.183 vs threshold 0.080, output identical in all runs. Raw: `siminfeng/experiments/jetson/OM/J-OM13/`.
- **Run 4 (recorded fallback):** 903.95 → 785.22 ms/token, one lab run per endpoint.
Ratios are never multiplied across steps.

## Files
`demo-final.mp4`, `recording/seg{1,2,3}.{typescript,timing}`, `results.json` (all identities and ids), `cards/*.png`, `SHA256SUMS`, `LAUNCH-REPLAY.md`, `RSI-HANDOFF.md`; decision trail in `docs/demo/WORKLOG.md`.
