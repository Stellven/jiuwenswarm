# Method: paired accuracy with planned checkpoints

The node owes one decision: does the candidate (the Q2 pack) lose less than the pinned margin of accuracy
against the reference (the NVFP4 pack) on a generally accepted benchmark? `verify` gives it at stage
`runtime acceptance` from the per-question rows. Keep the state file, both server logs and the driver log.

## Why scoring, not generation

On the DGX Spark, Muse with CPU-resident experts decodes at about 0.3 (NVFP4) to 0.85 (Q2) tokens per second,
so a generated answer costs minutes per question. Prefill costs about one pass over the streamed experts per
micro-batch, almost regardless of how many tokens the batch holds. So: score the next-token distribution after
`Answer:` (one token, `n_predict 1`, top-20 logprobs) and serve 16 slots so ~16 questions share one prefill pass.
Measured on Q2: see VALIDATION.md.

What this measures: zero-shot knowledge and answer selection without reasoning (the lm-evaluation-harness
MMLU form). It is the standard way to compare a quantized model with its source; reasoning-heavy tasks need
generation and are out of scope here.

## Steps

1. `order`: every MMLU test question (14,042) in one seeded shuffle (default seed 20261125). Both arms and any
   extension of the run use this order; the digest goes in the state.
2. Score the candidate up to a checkpoint, then the reference over the same questions (fewest server loads:
   B to 160, A to 160, and only if undecided B to 430, A to 430). Each row keeps the canonical prompt's sha256,
   the A-D probabilities, the letter mass, the pick and whether it is correct.
3. At each planned checkpoint (50, 100, 160, 250, 430 paired questions) compute the Newcombe paired interval of
   the loss `acc(A) - acc(B)` with the constant critical value `z = 2.65` and stop at the first decision:
   `pass` when the upper bound is below the margin, `fail` when the lower bound is above it; at 430 report the
   interval without a verdict.
4. `verify` with the state, the dataset and the contract's margin.

## Planning

Precision is set by the flip rate (questions exactly one arm gets right), not by accuracy:
`n ≈ 1.96² × flips / margin²` for one look. 10% flips need about 154 questions for ±5 points and 427 for ±3.
The first checkpoints report the observed flip rate; extend the order (not a new sample) if the run ends
undecided at 430.

## Why these constants

Looking at every checkpoint with z = 1.96 inflates the chance of a wrong pass. A Pocock-type constant boundary
for these five looks is 2.453 under the normal approximation; simulating this exact rule (Newcombe intervals,
true loss = margin, flip rates 6-20%) gave 3.0-3.5% wrong passes at 2.453 and 2.0-2.4% at 2.65, so 2.65 keeps
it at or under the nominal one-sided 2.5%. O'Brien-Fleming boundaries (5.8 at 50 questions) almost never stop
early, which defeats the purpose of checkpoints here.

## Also reported (not gates)

Answer agreement (same argmax letter) and the mean total-variation distance between the two arms' A-D
distributions: continuous, paired and far more sensitive than right/wrong flips. They show damage long before
the accuracy interval can.

## Scope of a pass

A pass says: on MMLU zero-shot letter scoring, the candidate loses less than the margin, with at most 2.5%
chance of a wrong pass. It says nothing about generation quality, long contexts, other languages or tasks,
and nothing about arms that change numerics differently (each needs its own run or a parity check against an
arm that has one).
