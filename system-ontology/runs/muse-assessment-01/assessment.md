# Assessment before build: Engine for Muse Spark Open on DGX Spark (proposed)

Design `sys/muse-on-spark` · model `model/muse-spark-open` · hardware `hw/dgx-spark` · environment `env/dgx-spark-strata-reported` · target spec `spec/muse-spark-open-on-dgx-spark/target`.

**How to read this.** Nothing was built or run. Every figure is arithmetic on the descriptions. Speeds are ceilings: a real engine is slower. Times are floors: a real engine takes longer. Where a quantity is not known it is varied over a stated range. Section 6 lists what must be measured to narrow the ranges.

## 1. What the model asks of the machine

| Quantity | Value | How it is known |
|---|---|---|
| Experts | 62 layers x 256 = 15,872; each token uses 8 per layer | vendor stated |
| All expert weights | 399.5 GB | derived |
| One expert | 25.2 MB | derived |
| Weights every token uses | 8.5 GB | derived |
| Expert weights one token reads | 8 x 62 x 25.2 MB = 12.48 GB | derived |
| Memory budget | 80 GB of `mem0` (130.6 GB allocatable, reported) | proposed |
| Memory bandwidth | 273 GB/s | vendor_stated |

The experts are 5.0 times the memory budget. They cannot be held in memory; `comp/muse/expert-cache` holds a part and `comp/muse/storage-reader` reads the rest from storage when routed.

## 2. Storage

The prepared files take 408 GB. While `comp/muse/preparation` runs, the published checkpoint and the prepared files are both present: 816 GB. The machine's storage is 4000 GB on its largest configuration; smaller configurations exist.

**Result:** fits on the largest configuration. A machine with less than 900 GB of storage needs the checkpoint prepared elsewhere.

## 3. Memory plan: how large the expert cache can be

Budget minus weights every token uses (8.5 GB), attention state, staging (0.40 GB) and a reserve (2.0 GB). The smallest cache the design starts with is the experts of one step, 12.5 GB. Decided by `comp/muse/startup-memory-sizing`; consumed by `comp/muse/expert-cache` and `comp/muse/kv-store`.

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

A routed expert that is not cached is read from storage first. The share found in the cache depends on how unevenly the experts are used. The table assumes the cache holds exactly the most used experts of every layer, and that reads overlap fully with computation. Constrains `comp/muse/expert-dispatch`, `comp/muse/cache-policy`, `comp/muse/resume-decision`, `comp/muse/storage-reader`.

**Largest cache: 17% of experts cached** (context 8,192, attention state one eighth of that).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Ceiling at 1.50 GB/s | Ceiling at 3.00 GB/s | Ceiling at 6.00 GB/s |
|---|---|---|---|---|---|
| 0 (even) | 17% | 10.39 GB | 0.14 tok/s | 0.29 tok/s | 0.58 tok/s |
| 0.8 | 58% | 5.28 GB | 0.28 tok/s | 0.57 tok/s | 1.14 tok/s |
| 1.2 | 82% | 2.23 GB | 0.67 tok/s | 1.35 tok/s | 2.70 tok/s |

**Smallest cache: 9% of experts cached** (context 131,072, attention state one eighth of that).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Ceiling at 1.50 GB/s | Ceiling at 3.00 GB/s | Ceiling at 6.00 GB/s |
|---|---|---|---|---|---|
| 0 (even) | 9% | 11.37 GB | 0.13 tok/s | 0.26 tok/s | 0.53 tok/s |
| 0.8 | 46% | 6.71 GB | 0.22 tok/s | 0.45 tok/s | 0.89 tok/s |
| 1.2 | 74% | 3.20 GB | 0.47 tok/s | 0.94 tok/s | 1.87 tok/s |

**Result:** between 0.13 and 2.70 tokens per second, as a ceiling. The spread comes almost entirely from two numbers nobody has measured: how unevenly this model uses its experts, and how fast this machine's storage reads.

What a given speed requires:

| Target | Share that must be found in cache at 1.50 GB/s | Share that must be found in cache at 3.00 GB/s | Share that must be found in cache at 6.00 GB/s |
|---|---|---|---|
| 0.5 tok/s | 76% | 52% | 4% |
| 1 tok/s | 88% | 76% | 52% |
| 2 tok/s | 94% | 88% | 76% |
| 5 tok/s | 98% | 95% | 90% |

With even use, the share found in the cache equals the share cached (9% to 17%). Reaching 1 token per second therefore needs either strongly uneven use, or fewer bytes per expert, or both.

## 5. Time to first token

A prompt is read in chunks, one layer at a time, so an expert routed by many tokens of a chunk is read once (`comp/muse/prompt-path`). But the tokens of a chunk together route to most of a layer's 256 experts: with even use, 100 tokens already reach 96% of them. The table gives the bytes read from storage for one prompt read as a single chunk, and the time that alone takes, for the largest cache.

| Prompt (tokens) | Use of experts | Read from storage | Floor at 1.50 GB/s | Floor at 3.00 GB/s | Floor at 6.00 GB/s |
|---|---|---|---|---|---|
| 100 | 0 (even) | 319 GB | 213 s | 106 s | 53 s |
| 100 | 1.2 | 150 GB | 100 s | 50 s | 25 s |
| 1,000 | 0 (even) | 334 GB | 223 s | 111 s | 56 s |
| 1,000 | 1.2 | 328 GB | 219 s | 109 s | 55 s |
| 10,000 | 0 (even) | 334 GB | 223 s | 111 s | 56 s |
| 10,000 | 1.2 | 334 GB | 223 s | 111 s | 56 s |

**Result:** between 25 and 223 seconds before the first token, as a floor, for a prompt that shares nothing with an earlier one. A prompt of a thousand tokens reads most of the expert file once whatever the cache holds. This makes `comp/muse/parked-conversations`, `comp/muse/session-files`, `comp/muse/resume-decision` essential and not optional: a continued conversation skips this cost for the shared prefix.

## 6. What is not known, and how to find out

| Unknown | Treated here as | How to settle it | Components it decides |
|---|---|---|---|
| Storage read rate of the target machine | assumed 1.5,3,6 GB/s | run `tools/spark_kit/probe.py` on the machine | `comp/muse/storage-reader`, `comp/muse/expert-source` |
| How unevenly the model uses its experts | assumed Zipf exponent 0,0.8,1.2 (0 is even use) | record routing on any machine that can run the reference model, over the benchmark's prompts | `comp/muse/engine-diagnostics`, `comp/muse/cache-policy`, `comp/muse/resume-decision` |
| Attention state per token | between 0.25 and 2.03 MB | read the model's config.json | `comp/muse/kv-store`, `comp/muse/startup-memory-sizing` |
| Context length the engine must offer | tabulated for 8192,32768,131072 tokens | a decision of the project | `comp/muse/startup-memory-sizing` |

Assumptions made:

- Size of the expert weights: 399.5 GB (derived). Assumes the 42B active parameters are all the non-expert parameters plus 8 of 256 experts per layer. Then experts E and the rest S satisfy E + S = 816B and E/32 + S = 42B, giving E = 799.0B and S = 17.0B. At 4 bits per parameter (NVFP4) the experts are 399.5 GB, about 25.2 MB each. The true value is in the weight file headers.
- Size of the weights every token uses: 8.5 GB (derived). 17.0B non-expert parameters under the same assumption, at 4 bits. It includes the embedding table and the output head. If these are kept at 16 bits the figure is 34 GB.
- Reserve left free: 2.0 GB. Staging area: 16 experts.

## 7. Constraints this assessment adds to the design

These follow from the arithmetic above. They are conditions the engine's own parts must meet, not requirements of the project.

| Constraint | Applies to |
|---|---|
| The cache is never smaller than the experts of one step: 496 experts, 12.5 GB | `comp/muse/startup-memory-sizing`, `comp/muse/expert-cache` |
| The staging area holds at least the 8 experts one token can route in a layer | `comp/muse/storage-reader` |
| Reads of a layer's missed experts are issued before its cached experts are computed | `comp/muse/expert-dispatch` |
| Attention state for the configured context plus all fixed holdings stays within 80 GB | `comp/muse/startup-memory-sizing`, `comp/muse/kv-store` |
| Reads do not pass through the operating system's page cache, or that cache is counted in the budget | `comp/muse/expert-source` |
| Each expert is one contiguous range on storage | `comp/muse/preparation`, `comp/muse/expert-layout` |
| The engine records how often each expert is routed, from its first run | `comp/muse/engine-diagnostics` |

## 8. Summary

- **Can it run?** Yes on memory and storage, for contexts up to the rows of Section 3 that fit.
- **How fast, at best?** 0.13 to 2.70 tokens per second while generating; never above 13.0.
- **What hurts most?** The first token of a new prompt: 25 to 223 seconds at the least.
- **What decides the outcome?** How unevenly the model uses its experts, and the storage read rate. Both can be measured before the engine exists.
- **What would change the picture?** Fewer bytes per expert (lower precision, which changes output and needs permission), omitting low-ranked experts (also changes output), or drafting (postponed in this design until a miss is priced).
- **What the project still has to decide:** the target spec has 12 blocking gaps; run `python tools/so_check.py check spec/muse-spark-open-on-dgx-spark/target` for the list.
