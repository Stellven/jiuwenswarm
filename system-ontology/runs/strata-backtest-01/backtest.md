# Back-test: Strata on `hw/dgx-spark`

Description `sys/strata` and its spec `spec/qwen-flash-on-dgx-spark/strata-like`, against what the project itself reports (`evidence/strata-on-spark/reported`, strata docs/DGX_SPARK_LINUX.md:70-100).

**What this is.** The assessment of a designed engine uses two pieces of arithmetic. Here the same arithmetic is applied to an engine that exists, on a machine where its own project reports measurements. We did not run the engine; the measurements are the project's. Nothing was adjusted to make the figures agree.

## 1. Speed ceiling from the bytes a token reads

Each token uses 10 of 512 experts in each of 48 layers. With every routed expert in memory, a token reads its experts and at most all other weights once, and memory bandwidth (273 GB/s) bounds how often that can happen per second. This is the formula of Section 4 of the Muse assessment.

| Weight pack | One expert | Bytes read per token | Ceiling by our arithmetic | Reported by the project | Reported / ceiling |
|---|---|---|---|---|---|
| IQ3_S | 2.05 MB | 5.84 GB | 46.8 tok/s | 45.2 to 48.5 tok/s | 0.97 to 1.04 |
| NVFP4 | 2.77 MB | 6.18 GB | 44.1 tok/s | 38.4 to 42.8 tok/s | 0.87 to 0.97 |

**Result:** the reported speeds are 0.87 to 1.04 times our figure. The arithmetic gives the right order of magnitude.

How far this goes, and where it stops:

- This engine drafts several tokens and checks them in one pass, so one pass over the weights can yield more than one token. Our figure is per pass. A reported speed slightly above it is therefore possible, and the closeness of the two is partly coincidence. The Muse design has no drafting, so there the figure is a true ceiling.
- "At most all other weights" overstates what a token reads: the embedding table is read one row at a time. That pushes our figure down.
- On this machine the engine reads nothing from storage while generating. The Muse assessment is dominated by storage reads, which this back-test does not exercise. It tests the memory part of the arithmetic only.

## 2. Memory accounting

Everything our description says the engine holds in `mem0`, added up, against what the machine has (130.6 GB reported allocatable) and what the project reports as left free after start.

| Held | Amount | From |
|---|---|---|
| `expert_weights` | 50.30 GB | binding, reclaimable_mapping |
| `ngram_table` | 28.80 GB | binding, pinned |
| `shared_weights` | 4.86 GB | binding, pinned |
| startup-memory-sizing: the reserve left free after loading | 0.73 GB | composition |
| mtp_drafter: draft-layer weights, its 512 experts, its K/V, draft-head subset, draft logits, buffers and graphs | 0.90 GB | composition |
| engine-command-loop: One session state per batch slot, only when batch slots are configured | 0.60 GB | composition |
| checkpoint-chain: Up to 6 checkpoints of running state | 0.71 GB | composition |
| **Total our description accounts for** | **86.9 GB** | |

| Weight pack | Reported free after start | So the engine and system hold | Our description accounts for | Not accounted for |
|---|---|---|---|---|
| IQ3_S | 1.1 GB | 129.5 GB | 86.9 GB (67%) | 42.6 GB |
| NVFP4 | 1.3 GB | 129.3 GB | 75.8 GB (59%) | 53.5 GB |

**Result:** our description accounts for 59% to 67% of the memory in use. The rest is held by things our description names but gives no amount for:

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

The largest of these is the attention state for a 64K context. This is the same unknown that Section 3 of the Muse assessment varies over a range, and the back-test shows it is not small: tens of GB on this engine.

## 3. What the description says about this machine, to be checked on it

These statements come from the project's document, not from a run. Running the engine on the machine and reading its diagnostics would confirm or refute each.

| Component | Our description says | How to check on the machine |
|---|---|---|
| `comp/strata/adaptive-tier` | inactive: Every expert is in the cache, so there is no absent expert to swap in. | its counters stay at zero during a run |
| `comp/strata/host-to-device-transfer` | inactive: Every expert is in the cache after startup, so nothing is fetched for a window and nothing is swapped. | its counters stay at zero during a run |
| `comp/strata/session-loop` | inactive: Runs only with the canonical Q2_0 pack; whether that pack is used on this target was not established. | its counters stay at zero during a run |
| `comp/strata/cpu-expert-pool` | inactive: Taken from the earlier description, not from the token-path notes: all experts are resident on this target, so no layer has CPU work. The pool is still built and its workers sleep. | its counters stay at zero during a run |
| `comp/strata/dflash2-drafter` | inactive: Opt-in, not loaded by default. When loaded on this card class (compute capability 12.1) its window is capped at 6 rows (strata include/strata/core/draft_cap.hpp:19-24). | its counters stay at zero during a run |
| `comp/strata/slot-scheduler` | inactive: Batch slots are off unless the configuration asks for them. Whether setup recommends them on this machine was not established. | its counters stay at zero during a run |
| `comp/strata/replica-router` | inactive: Opt-in, and it needs at least two groups of cards; this target has one GPU. | its counters stay at zero during a run |
| expert cache | holds 24,576 of 24,576 experts | the engine's start-up line reports the slot count |

## 4. What this back-test shows and does not show

- **Shows:** the speed arithmetic is right to within a factor of 1.1 on a real engine; the memory accounting covers most but not all of what a real engine holds, and the missing part is identified.
- **Does not show:** anything about storage reads, cache hit rates or time to first token, which decide the Muse result.
- **Next:** run this engine on the machine with the benchmark, so that Section 3 rests on a run and the attention state gets a measured size.
