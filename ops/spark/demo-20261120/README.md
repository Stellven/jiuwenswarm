# Spark GB10 demo, 2026-11-20

On the DGX Spark GB10, JiuwenSwarm applied five builder Capability Capsules to stock llama.cpp running DeepSeek V4.1 Flash. Each change was gate-checked, then measured in a memory-capped lab against stock llama.cpp with the same memory budget and against Strata.

- **Engineering report:** [report.md](report.md).
- **Headline numbers, with their ledger rows:** [OPS/final-headlines.json](OPS/final-headlines.json).
- **Overnight records:** [OPS/](OPS/) holds STATUS (the timeline), DECISIONS (who decided what, including the owner's steering), BLOCKERS, LEDGER (one row for every capped run), and the iteration reports and receipts that report.md links to.
- **Task contract:** [`star-deepseek-v1`](../../../jiuwenswarm/factory/contracts/star-deepseek-v1.md).
- **Capsules:** [`jiuwenswarm/factory/ccs/`](../../../jiuwenswarm/factory/ccs/).

## Headline

Cache CC v1.3 (commit ad2130b0) was compared with stock A+ (stock plus its native MoE cache) at the same 60 GiB bank. The run was a quiet A-B-B-A with 10 pairs per prompt size.

- **Time to first token:** 27.08 s sooner at 512 tokens and 92.07 s sooner at 2048, on a running server. Every pair was faster.
- **Decode:** unchanged.
- **Startup:** the seeded server takes about 88 s longer to start.
- **Direct-seed v1.4:** measured only at 30 GiB, where it reached parity.

**Negative results:**
- The demand predictor and the batch layout mapper did not help.
- D (all five combined) was effectively recorder plus placement, because the other gates declined.

## Not in this repository

These are kept on branch `demo/cc-star-ui-20261120` and in an offline archive:
- the factory evidence stores and the native factory export
- raw engine logs, the UI screenshots and the presentation deck

The curated replay shown in the Factory runs UI is rebuilt from the factory homes with `scripts/spark/build_demo_replays.py` on that branch.
