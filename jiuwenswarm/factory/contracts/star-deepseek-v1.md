# Star DeepSeek contract v1

The task is to apply five builder Capability Capsules to stock llama.cpp at
`9048bad8d6e3a0f9f1726e238e451181c7e02613` on DGX Spark GB10, CUDA 13, SM121.
The factory records the work; the lead engineer runs inference through
`~/predemo-spark/bin/capped`. The existing factory lab cannot launch this
contract. This is a retarget of the Satay `star-prefill-v0` contract, not M1
machinery or an accuracy benchmark.

Use the converted six-shard DeepSeek V4.1 Flash pack listed in
[the raw contract](star-deepseek-v1.json). The Strata yardstick runs the same
weights in its native pack. Retained conversion receipts establish the intake
lineage; this document does not claim to have rehashed all converted shards.

Use fixed text in [512.txt](../../../ops/spark/prompts/512.txt) and
[2048.txt](../../../ops/spark/prompts/2048.txt), including the fixed no-thinking
chat template. [The prompt manifest](../../../ops/spark/prompts/MANIFEST.json)
records token IDs and template identity. Runtime server token counts must be
checked. Generate 32 tokens, temperature 0, seed 1, with prompt caching disabled.
Discard the first request after each engine load and record cold load separately.

Compare **S** (Strata fair profile), **A** (stock `-lm mmap --cpu-moe`, all other
engine defaults), **A+** (A with the documented native MoE cache selected by its
tuning script), **C1–C5** (one capsule product each) and **D** (all five).
Record every deviation from A explicitly. Each engine gets the same 100 GiB,
eight-CPU cap, 110 GiB available-memory admission and 8 GiB watchdog guard.
Timed cells require load below 1.0 with no builds running.

The primary outcome is client TTFT at 512 and 2048 prompt tokens, five warm
repeats in ABBA order. Gap closed is `(TTFT_A − TTFT_X)/(TTFT_A − TTFT_S)`.
Also report inverse TTFT against A and A+, decode rate, sampled peak memory,
load time and confidence intervals. Speed targets are targets, not promises.

Each capsule must pass its verifier and frozen scorer S1–S5/S5L on the small
fixture, preserve gate-unset greedy output, and show the gate-set activation
marker. Record failures and no-gain outcomes. Until reference parity is frozen,
the null fields in the raw contract remain visibly unfrozen. Do not infer
runtime acceptance from a successful source or build check.

The system ontology is the owner-supplied [pinned manifest](../../../../inputs/ontology/SHA256SUMS):
[design](../../../../inputs/ontology/system-ontology-design.en.md),
[dictionary](../../../../inputs/ontology/unified-dictionary.md),
[metadata alignment](../../../../inputs/ontology/metadata-alignment.md),
[term alignment](../../../../inputs/ontology/term-alignment-for-review.md),
[worked example](../../../../inputs/ontology/EXAMPLE.md), and
[overview](../../../../inputs/ontology/20261117%20Unified%20overview%20prepresentation.mmd).
Each builder's `ONTOLOGY.yaml` supplies its unchanged local slice. No ontology
redesign or intent compiler is part of this task.

The five source capsules are **1.1.1**. Canonical transport copies are **1.1.2**:
only manifest kind fields moved into passive `roles.json`; methods, ontology,
samples, acceptance text and verifiers remain byte-identical. The old/new
sealed digests are in `ccs/star-transport-migration.json`. This migration does
not establish Spark runtime support: the source materials still name the
original Jetson host, and the Spark task supplies the explicit target override.
