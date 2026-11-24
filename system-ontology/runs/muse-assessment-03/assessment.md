# Assessment before build: Engine for Muse Spark Open on DGX Spark (proposed)

Design `sys/muse-on-spark` · model `model/muse-spark-open` · hardware `hw/dgx-spark` · environment `env/dgx-spark-measured` · target spec `spec/muse-spark-open-on-dgx-spark/target`.

**How to read this.** Nothing was built or run. Every figure is arithmetic on the descriptions. Speeds are ceilings: a real engine is slower. Times are floors: a real engine takes longer. Where a quantity is not known it is varied over a stated range. Section 6 lists what must be measured to narrow the ranges.

## Read this first: what these figures can and cannot say

1. **The low speed comes from the size of the model against this machine, not from this design.** The expert weights are 5.0 times the memory budget, and one token reads 12.5 GB of them. If all of that came from storage, one token would take 2.6 seconds (0.38 tokens per second). With all of it already in memory, the limit is 13.0 tokens per second. Any engine for this model on this machine lies between these two figures. A design decides only where: by how much of what a token needs is in memory when it is needed.
2. **The figures are bounds, not predictions.** Only the time to move bytes is counted. Computation, scheduling and waiting are left out. Reads are taken to overlap computation fully, and the cache to hold the right experts from the start. A real engine is slower on every one of these, by an amount this assessment cannot give.
3. **Half of the arithmetic has been compared with a real engine; the half that decides this result has not.** The memory part was applied to an existing engine with published measurements on the same machine (`runs/strata-backtest-01/backtest.md`): the reported speeds were 0.87 to 1.04 times the figure. That engine reads nothing from storage while generating. Here storage reads decide the result, and that part has not been compared with any engine. No engine for this design exists, so nothing here has been measured on it.
4. **3 quantities are not known and 2 are derived, not read from the model's files.** Not known: how unevenly the model uses its experts; attention state per token; context length the engine must offer. Derived: the size of the expert weights and the size of the weights every token uses. Section 6 says how each can be settled. Until then the ranges cannot be narrowed by more arithmetic.

## 1. What the model asks of the machine

| Quantity | Value | How it is known |
|---|---|---|
| Experts | 62 layers x 256 = 15,872; each token uses 8 per layer | vendor stated |
| All expert weights | 399.5 GB | derived |
| One expert | 25.2 MB | derived |
| Weights every token uses | 8.5 GB | derived |
| Expert weights one token reads | 8 x 62 x 25.2 MB = 12.48 GB | derived |
| Memory budget | 80 GB of `mem0` (126.2 GB allocatable, measured) | proposed |
| Storage read rate, one large sequential read | 4.81 GB/s | measured |
| Storage read rate, 1 ranges at a time, each 25 MB at a random place | 4.58 GB/s | measured |
| Storage read rate, 8 ranges at a time, each 25 MB at a random place | 4.75 GB/s | measured |
| Storage read rate, 16 ranges at a time, each 25 MB at a random place | 4.79 GB/s | measured |
| Storage read rate, 32 ranges at a time, each 25 MB at a random place | 4.82 GB/s | measured |
| Memory bandwidth | 273 GB/s | vendor_stated |

The experts are 5.0 times the memory budget. They cannot be held in memory; `comp/muse/expert-cache` (type `expert-cache`) holds a part and `comp/muse/storage-reader` (type `expert-fetch`) reads the rest from storage when routed.

## 2. Storage

The prepared files take 408 GB. While `comp/muse/preparation` (type `model-conversion`) runs, the published checkpoint and the prepared files are both present: 816 GB. The machine's storage is 2015 GB as reported by this machine.

**Result:** fits. A machine with less than 900 GB of storage needs the checkpoint prepared elsewhere.

## 3. Memory plan: how large the expert cache can be

Budget minus weights every token uses (8.5 GB), attention state, staging (0.40 GB) and a reserve (2.0 GB). The smallest cache the design starts with is the experts of one step, 12.5 GB. Decided by `comp/muse/startup-memory-sizing` (type `memory-planning`); consumed by `comp/muse/expert-cache` (type `expert-cache`) and `comp/muse/kv-store` (type `positional-state-store`).

| Context (tokens) | Attention state per token | Attention state | Expert cache | Experts cached | Share of all experts |
|---|---|---|---|---|---|
| 8,192 | as wide as the hidden size | 16.6 GB | 52.5 GB | 2,084 | 13% |
| 8,192 | one eighth of that | 2.1 GB | 67.0 GB | 2,663 | 17% |
| 32,768 | as wide as the hidden size | 66.6 GB | **does not fit** | — | — |
| 32,768 | one eighth of that | 8.3 GB | 60.8 GB | 2,415 | 15% |
| 131,072 | as wide as the hidden size | 266.3 GB | **does not fit** | — | — |
| 131,072 | one eighth of that | 33.3 GB | 35.8 GB | 1,423 | 9% |

**Result:** the cache holds between 9% and 17% of the experts in the cases that fit. The context length is a first-order choice: it is taken from the same memory as the cache. If the embedding table and output head stay at 16 bits, subtract a further 25 GB from every row.

## 4. Decode speed

Each token reads 12.48 GB of expert weights and at most 8.5 GB of other weights. With every routed expert already in memory, memory bandwidth alone limits the engine to **13.0 tokens per second**. That is the ceiling no cache policy can exceed.

A routed expert that is not cached is read from storage first. The share found in the cache depends on how unevenly the experts are used. The table assumes the cache holds exactly the most used experts of every layer, and that reads overlap fully with computation. Constrains `comp/muse/expert-dispatch` (type `expert-dispatch`), `comp/muse/cache-policy` (type `residency-policy`), `comp/muse/resume-decision` (type `prefix-reuse`), `comp/muse/storage-reader` (type `expert-fetch`).

**Largest cache: 17% of experts cached** (context 8,192, attention state one eighth of that).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Ceiling at 4.75 GB/s | Ceiling at 4.82 GB/s |
|---|---|---|---|---|
| 0 (even) | 17% | 10.39 GB | 0.46 tok/s | 0.46 tok/s |
| 0.8 | 58% | 5.28 GB | 0.90 tok/s | 0.91 tok/s |
| 1.2 | 82% | 2.23 GB | 2.13 tok/s | 2.17 tok/s |

**Smallest cache: 9% of experts cached** (context 131,072, attention state one eighth of that).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Ceiling at 4.75 GB/s | Ceiling at 4.82 GB/s |
|---|---|---|---|---|
| 0 (even) | 9% | 11.37 GB | 0.42 tok/s | 0.42 tok/s |
| 0.8 | 46% | 6.71 GB | 0.71 tok/s | 0.72 tok/s |
| 1.2 | 74% | 3.20 GB | 1.48 tok/s | 1.51 tok/s |

**Result:** between 0.42 and 2.17 tokens per second, as a ceiling. With the storage rate measured, the spread now comes mostly from one number nobody has measured: how unevenly this model uses its experts.

What a given speed requires:

| Target | Share that must be found in cache at 4.75 GB/s | Share that must be found in cache at 4.82 GB/s |
|---|---|---|
| 0.5 tok/s | 24% | 23% |
| 1 tok/s | 62% | 61% |
| 2 tok/s | 81% | 81% |
| 5 tok/s | 92% | 92% |

With even use, the share found in the cache equals the share cached (9% to 17%). Reaching 1 token per second therefore needs either strongly uneven use, or fewer bytes per expert, or both.

## 5. Time to first token

A prompt is read in chunks, one layer at a time, so an expert routed by many tokens of a chunk is read once (`comp/muse/prompt-path` (type `prompt-reading`)). But the tokens of a chunk together route to most of a layer's 256 experts: with even use, 100 tokens already reach 96% of them. The table gives the bytes read from storage for one prompt read as a single chunk, and the time that alone takes, for the largest cache.

| Prompt (tokens) | Use of experts | Read from storage | Floor at 4.75 GB/s | Floor at 4.82 GB/s |
|---|---|---|---|---|
| 100 | 0 (even) | 319 GB | 67 s | 66 s |
| 100 | 1.2 | 150 GB | 31 s | 31 s |
| 1,000 | 0 (even) | 334 GB | 70 s | 69 s |
| 1,000 | 1.2 | 328 GB | 69 s | 68 s |
| 10,000 | 0 (even) | 334 GB | 70 s | 69 s |
| 10,000 | 1.2 | 334 GB | 70 s | 69 s |

**Result:** between 31 and 70 seconds before the first token, as a floor, for a prompt that shares nothing with an earlier one. A prompt of a thousand tokens reads most of the expert file once whatever the cache holds. This makes `comp/muse/parked-conversations` (type `prefix-reuse`), `comp/muse/session-files` (type `session-persistence`), `comp/muse/resume-decision` (type `prefix-reuse`) essential and not optional: a continued conversation skips this cost for the shared prefix.

## 6. What is not known, and how to find out

| Unknown | Treated here as | How to settle it | Components it decides |
|---|---|---|---|
| How unevenly the model uses its experts | assumed Zipf exponent 0,0.8,1.2 (0 is even use) | record routing on any machine that can run the reference model, over the benchmark's prompts | `comp/muse/engine-diagnostics` (type `telemetry`), `comp/muse/cache-policy` (type `residency-policy`), `comp/muse/resume-decision` (type `prefix-reuse`) |
| Attention state per token | between 0.25 and 2.03 MB | read the model's config.json | `comp/muse/kv-store` (type `positional-state-store`), `comp/muse/startup-memory-sizing` (type `memory-planning`) |
| Context length the engine must offer | tabulated for 8192,32768,131072 tokens | a decision of the project | `comp/muse/startup-memory-sizing` (type `memory-planning`) |

Assumptions made:

- Size of the expert weights: 399.5 GB (derived). Assumes the 42B active parameters are all the non-expert parameters plus 8 of 256 experts per layer. Then experts E and the rest S satisfy E + S = 816B and E/32 + S = 42B, giving E = 799.0B and S = 17.0B. At 4 bits per parameter (NVFP4) the experts are 399.5 GB, about 25.2 MB each. The true value is in the weight file headers.
- Size of the weights every token uses: 8.5 GB (derived). 17.0B non-expert parameters under the same assumption, at 4 bits. It includes the embedding table and the output head. If these are kept at 16 bits the figure is 34 GB.
- Storage read rate: measured for scattered ranges of one expert's size: 4.75 GB/s with 8 in flight (one token routes 8 experts in a layer), 4.82 GB/s at best with 32 in flight. Measured on an idle machine with a test file; a real engine shares the device with nothing else in this figure.
- Reserve left free: 2.0 GB. Staging area: 16 experts.

## 7. Constraints this assessment adds to the design

These follow from the arithmetic above. They are conditions the engine's own parts must meet, not requirements of the project.

| Constraint | Applies to |
|---|---|
| The cache is never smaller than the experts of one step: 496 experts, 12.5 GB | `comp/muse/startup-memory-sizing` (type `memory-planning`), `comp/muse/expert-cache` (type `expert-cache`) |
| The staging area holds at least the 8 experts one token can route in a layer | `comp/muse/storage-reader` (type `expert-fetch`) |
| Reads of a layer's missed experts are issued before its cached experts are computed | `comp/muse/expert-dispatch` (type `expert-dispatch`) |
| Attention state for the configured context plus all fixed holdings stays within 80 GB | `comp/muse/startup-memory-sizing` (type `memory-planning`), `comp/muse/kv-store` (type `positional-state-store`) |
| Reads do not pass through the operating system's page cache, or that cache is counted in the budget | `comp/muse/expert-source` (type `expert-source`) |
| Each expert is one contiguous range on storage | `comp/muse/preparation` (type `model-conversion`), `comp/muse/expert-layout` (type `model-loading`) |
| The engine records how often each expert is routed, from its first run | `comp/muse/engine-diagnostics` (type `telemetry`) |

## 8. Where each quantity is decided

Every quantity the arithmetic above uses is decided in one of four places: by the model, by the machine, by the target, or by a choice that a node type leaves to whoever builds the engine (node types draft 0.9). Only the last kind is a design decision. The first three are given, or still to be measured or set.

| Quantity | Used here as | Decided by |
|---|---|---|
| Size of the expert weights, and how many a token uses | 399.5 GB; 8 of 256 in each of 62 layers (derived) | the model |
| Weights every token uses | 8.5 GB (derived) | the model |
| Attention state per token | not known: between 0.25 and 2.03 MB | the model |
| How unevenly the experts are used | not known: Zipf exponent 0,0.8,1.2 | the model |
| Storage read rate | measured for scattered ranges of one expert's size: 4.75 GB/s with 8 in flight (one token routes 8 experts in a layer), 4.82 GB/s at best with 32 in flight | the machine |
| Memory bandwidth | 273 GB/s (vendor_stated) | the machine |
| Storage capacity | 2015 GB (reported by the machine) | the machine |
| Memory budget | 80 GB of `mem0` (proposed) | the target |
| Context length | not set: tabulated for 8192,32768,131072 tokens | the target |

Design decisions, by the node type that leaves them open:

| Quantity | Used here as | Node type | Its choice | Component of this design | How the design settles it |
|---|---|---|---|---|---|
| Memory left free | 2.0 GB | `memory-planning` | the reserve left free | `comp/muse/startup-memory-sizing` | Memory left free for the operating system and for allocations not priced in advance. |
| Smallest cache the engine starts with | the experts of one step, 12.5 GB | `memory-planning` | the least a cache may be and still work | `comp/muse/startup-memory-sizing` | The smallest cache the engine will start with: at least the experts one step can route, 8 times 62. |
| Which experts the cache holds | the most used of every layer, the best any rule can do in steady state | `residency-policy` | part of the job of the type; not a listed choice | `comp/muse/cache-policy` | not recorded in the design |
| Staging area for experts being read | 16 experts, 0.40 GB | `expert-fetch` | part of the job of the type; not a listed choice | `comp/muse/storage-reader` | not recorded in the design |
| When a missed expert's read is issued | before the cached experts of the layer are computed, so that reads overlap fully with computation | `expert-dispatch` | part of the job of the type; not a listed choice | `comp/muse/expert-dispatch` | not recorded in the design |
| How a prompt is cut | one chunk, read one layer at a time | `prompt-reading` | chunk size | `comp/muse/prompt-path` | Tokens per chunk. Larger chunks amortise each expert read over more tokens but need more experts in memory at once. |
| Precision of the stored weights | as published, 4 bits; keeping the embedding table and the output head at 16 bits takes a further 25 GB | `model-conversion` | precision per kind of weight, and per layer where it differs | `comp/muse/preparation` | not recorded in the design |

What would change the picture, and whether the target allows it. The level is how far the change moves the output, as the node type states it.

| Change | Node type | In this design | Level | Does the target allow this level? |
|---|---|---|---|---|
| Fewer bytes per expert, by a lower precision of the expert weights | `model-conversion` | yes | `approximate` | not decided: the target's `allowed_transformations` is not set |
| Omitting low-ranked routed experts that are not in the cache | `expert-dispatch` | yes | `approximate` | not decided: the target's `allowed_transformations` is not set |
| Drafting several tokens and checking them in one step | `draft-verification` | no | `numeric` | not decided: the target's `allowed_transformations` is not set |

## 9. Summary

- **Can it run?** Yes on memory and storage, for contexts up to the rows of Section 3 that fit.
- **How fast, at best?** 0.42 to 2.17 tokens per second while generating; never above 13.0.
- **What hurts most?** The first token of a new prompt: 31 to 70 seconds at the least.
- **What decides the outcome?** How unevenly the model uses its experts, and the storage read rate. Both can be measured before the engine exists.
- **What would change the picture?** Fewer bytes per expert (lower precision, which changes output and needs permission), omitting low-ranked experts (also changes output), or drafting (postponed in this design until a miss is priced).
- **What the project still has to decide:** the target spec has 12 blocking gaps; run `python tools/so_check.py check spec/muse-spark-open-on-dgx-spark/target` for the list.
