# Back-test of the memory-bandwidth upper bound: Strata on `hw/dgx-spark`

Description `sys/strata`, its spec `spec/qwen-flash-on-dgx-spark/strata-like`, model `model/qwen3.8-flash-125b-a6b`, against what I measured (`evidence/strata-on-spark/measured-20261120`, runs/strata-measured-2026-11-20/iq3s (engine.log, the engine's own line per request; evidence-iq3s-2k.yaml and evidence-iq3s-4k.yaml, timed by the client)). I ran the engine. One start of the engine, nothing else running on the machine. Per prompt length 4 requests after 2 warm-up requests, new prompts, temperature 0, one request at a time. Context 64K, 8-bit attention state, drafting on, as its setup configures this machine. Prompts of 2,034 to 2,616 tokens with 128 tokens out, and of 4,480 to 5,394 tokens with 256 tokens out.

**What is compared.** The one figure of tools/so_assess.py that is an upper bound that needs no assumption about how the experts are used: memory bandwidth divided by the bytes one token surely reads, per pass over the weights, for one sequence. It is computed by the same function as in the assessment (`so_assess.model_facts`), so the bytes a token reads are defined the same way: the routed experts, every weight the description says each token reads in full, one row of the embedding table, and nothing whose per-token amount the description does not give. The engine reports tokens per second; its speed per pass over the weights is its speed divided by the tokens it produces per pass, which the evidence gives as more than one, so the two differ.

**Pass condition** (added to this program on 2026-11-18, after the result of its first run, Strata on `hw/dgx-spark` in `runs/strata-backtest-01`, was known; that run had no condition and could not fail): every measured speed divided by the fewest tokens per pass the evidence gives is at or below the bound of its weight pack. PASS if so, FAIL otherwise. A speed below the bound does not count against it: an upper bound says nothing about how much slower an engine is.

Tokens per pass: 2.25 to 2.84 tokens per pass, from the evidence (runs/strata-measured-2026-11-20/iq3s/engine.log, drafts accepted per request; Derived: tokens generated over the tokens that were not accepted drafts, taking every pass to give one token of the model besides the drafts it accepts. The engine's line gives 71 to 83 accepted drafts in 128 tokens and 151 to 157 in 256).

## 1. Upper bound and measured speeds

Bytes one token reads, as the assessment defines them:

| Weight | Size | Read by one token | Counted |
|---|---|---|---|
| `expert_weights` | per weight pack, below | 10 of 512 experts in each of 48 layers | yes |
| `shared_weights` | 4.86 GB | all of it | yes |
| `token_embedding` | 0.48 GB | one row | no: the size of one row cannot be derived |
| `output_head_weights` | 0.44 GB | all of it | yes |
| `ngram_table` | 28.80 GB | an amount the description does not give | no |
| `mtp_weights` | 0.82 GB | only when drafting | no |
| `dflash2_weights` | not given | only when drafting | no |

- `ngram_table` (28.8 GB) is read while generating, but the description does not say how much of it one token reads. It is not counted in the bytes a token reads (counting it would lower the upper bound) and not priced in the memory plan (holding it in memory would shrink the cache).
- `token_embedding`: one row is read per token, of a size the description does not allow to compute; it is not counted, so the true bytes per token are higher by one row.

The model description's own notes on the weights counted above. The program does not interpret them; where one says a size or the amount a token reads differs, the figures above do not reflect it:

- `shared_weights`: The whole set in the engine's canonical form. Native packs skip about 2.7 GiB of it. The weights every token uses, other than the embedding table and the output head listed below.
- `token_embedding`: One row is read per token; the engine places it apart from the other weights.
- `output_head_weights`: The one dense tensor the engine's startup sizing may move from fast to slow memory.

| Weight pack | One expert | Bytes read per token, at least | Upper bound per pass | Reported | Reported per pass | Reported / bound (tokens) | Reported per pass / bound |
|---|---|---|---|---|---|---|---|
| IQ3_S | 2.05 MB | 6.28 GB | 43.5 tok/s | 52.9 to 60.6 tok/s | 18.6 to 26.9 | 1.22 to 1.39 | 0.43 to 0.62 |

**Result: PASS.** Per pass the measured speeds are 0.43 to 0.62 times the bound. In tokens per second they are 1.22 to 1.39 times it.

What each ratio can show:

- **Per pass** compares like with like. A value above 1 would refute the bound, or the sizes or tokens per pass it rests on. A value at or below 1 is consistent with it and does not show how close it is: computation and the attention state read per token are not in the bound.
- **Tokens per second** compares a speed in tokens with a bound per pass. With drafting a value above 1 is possible and contradicts nothing; this ratio cannot show whether the bound holds.
- The evidence reports every expert in the cache for every pack, so the engine read no expert from storage here: the storage part of the assessment's arithmetic, its cache and hit-rate estimates and its first-token estimates are not tested by this back-test.

## 2. Memory accounting

Everything the description says the engine holds in `mem0`, added up, against what the machine has (127.2 GB, the memory figure of `env/dgx-spark-measured-20261119`) and what I measured as left free after start.

| Held | Amount | From |
|---|---|---|
| `expert_weights` | 50.30 GB | binding, reclaimable_mapping |
| `ngram_table` | 28.80 GB | binding, pinned |
| `shared_weights` | 4.86 GB | binding, pinned |
| startup-memory-sizing: the reserve left free after loading | 0.73 GB | composition |
| mtp_drafter: draft-layer weights, its 512 experts, its K/V, draft-head subset, draft logits, buffers and graphs | 0.90 GB | composition |
| engine-command-loop: One session state per batch slot, only when batch slots are configured | 0.60 GB | composition |
| checkpoint-chain: Up to 6 checkpoints of running state | 0.71 GB | composition |
| **Total the description gives an amount for** | **86.9 GB** | |

| Weight pack | Reported free after start | So the engine and the system hold | The description gives amounts for | Difference |
|---|---|---|---|---|
| IQ3_S | 2.1 GB | 125.2 GB | 86.9 GB (69% of it) | +38.2 GB |

Lookup table per pack: IQ3_S: `ngram_table` counted as 28.8 GB (the evidence: locked in memory).

**Result:** for IQ3_S the amounts the description gives come to 69% to 69% of the memory in use; 38.2 to 38.2 GB is held by the 19 items below, for which it gives no amount, or by the system.

Held, with no amount in the description:

- `attention_kv` (binding)
- `conversation_checkpoints` (binding)
- `parked_conversations` (binding)
- model-file-reader: whole-file read-only mapping while a shard is open
- weight-loader: one device range holding the kept dense tensors in engine form
- native-weight-loader: projection matrices, output head and token embedding in GGUF form
- expert-source: the arena: every routed expert plus one spare largest blob
- prompt_path: chunk buffers
- window-loop: the window arena and mapped staging
- layer-kernels: the session arena
- window-graphs: driver memory of the instantiated graphs
- ngram-reader: the table locked in memory when the start-up rule admits it
- lookup_drafter: token history and trigram table for max_context + 4096 tokens
- draft_verifier: commit stores, the commit graph, a small buffer for draft distributions
- prompt-builder: Vocabulary, merges and up to 4 kept prompts
- parked-conversations: Parked conversation images
- session-files: Buffers during a save or restore
- engine-diagnostics: Count maps and the manifest record
- server-metrics: 500 request rows, 128 events and 60 samples per hardware series

## 3. What the description says about this machine, to be checked on it

These statements come from the engine's log of the measured run.

| Component | The description says | How to check on the machine |
|---|---|---|
| `comp/strata/adaptive-tier` | inactive: Every expert is in the cache, so there is no absent expert to swap in. | its counters stay at zero during a run |
| `comp/strata/host-to-device-transfer` | inactive: Every expert is in the cache after startup, so nothing is fetched for a window and nothing is swapped. | its counters stay at zero during a run |
| `comp/strata/session-loop` | inactive: Runs only with the canonical Q2_0 pack; whether that pack is used on this target was not established. | its counters stay at zero during a run |
| `comp/strata/cpu-expert-pool` | inactive: Taken from the earlier description, not from the token-path notes: all experts are resident on this target, so no layer has CPU work. The pool is still built and its workers sleep. | its counters stay at zero during a run |
| `comp/strata/dflash2-drafter` | inactive: Opt-in, not loaded by default. When loaded on this card class (compute capability 12.1) its window is capped at 6 rows (strata include/strata/core/draft_cap.hpp:19-24). | its counters stay at zero during a run |
| `comp/strata/slot-scheduler` | inactive: Batch slots are off unless the configuration asks for them. Whether setup recommends them on this machine was not established. | its counters stay at zero during a run |
| `comp/strata/replica-router` | inactive: Opt-in, and it needs at least two groups of cards; this target has one GPU. | its counters stay at zero during a run |
| expert cache, IQ3_S | holds 24,576 of 24,576 experts (the evidence) | the engine's start-up line reports the slot count |
