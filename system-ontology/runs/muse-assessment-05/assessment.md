# Bounds and estimates for `model/muse-spark-open` on `hw/dgx-spark` within the target's 80 GB budget, for an engine that keeps part of the experts in memory

Model `model/muse-spark-open` · machine `hw/dgx-spark` · environment `env/dgx-spark-measured` · target `spec/muse-spark-open-on-dgx-spark/target` · design `sys/muse-on-spark` (node types only) · node types draft 0.9.

**What is assessed.** The figures are bounds and estimates for the model `model/muse-spark-open` on the machine `hw/dgx-spark` within the target's memory budget of 80 GB, for an engine of one architecture: the weights every token uses and part of the experts kept in memory, the rest read from storage when routed. The design `sys/muse-on-spark` contributes which node types it has and nothing else numeric: no figure changes when the design's decisions change, unless a decision gives a number this program reads (memory-planning: the reserve left free, memory-planning: the least a cache may be and still work, prompt-reading: chunk size; Section 2). In this run no decision of the design gave a number. This is not an assessment of the design's quality.

## Read this first: what these figures can and cannot say

0. **What they are about:** the model, the machine and the target's budget, for an engine that keeps the weights every token uses and part of the experts in memory and reads the rest from storage when routed. The design gives only which node types it has, and no number. No figure changes when its decisions change unless a decision gives a number this program reads. This is not an assessment of the design's quality.

1. **One figure is an upper bound that needs no assumption about how the experts are used:** 20.5 tokens per second, memory bandwidth over the bytes a token surely reads, for one sequence and one token per pass, with the weight sizes as the model states them (Section 2 says how each is known). Inside `shared_weights` the description gives no size to a part a token of this target does not read, so 6.84 GB of possibly read weights is left out of the bound: it is a true upper bound but may be loose by that much (the estimate counts it: 13.5 tokens per second). `token_embedding`, `output_head_weights` are sized at the bits of the expert weights because the model gives no bits for them: stored at more bits, the true bound is lower than this figure; at fewer, higher. With no expert in memory a token takes 2.6 s (0.39 tokens per second), a reference point, not a bound.

2. **Every other speed and time is an estimate under stated assumptions** (Section 6): each token's choice of experts independent of the previous token's, the cache holding the most used experts, reading fully overlapped and computation not counted. If successive tokens repeat experts, a cache that follows recent use finds more: the speed estimates are then not upper bounds and the first-token estimates not lower bounds.

3. **The figures are for the target's budget of 80 GB** (proposed); the environment reports 126.2 GB allocatable. They change with the budget, the reserve, the context lengths and the range of unevenness, each listed with its source in Section 2.

4. **Back-test** (`runs/strata-backtest-02`): the memory-bandwidth upper bound, computed the same way, was compared with the speeds the project of `sys/strata` reports for model `model/qwen3.8-flash-125b-a6b` on the same machine description as here. Condition: every reported speed / fewest tokens per pass <= bound (written 2026-11-18, after the first result was known). Per pass the reported speeds are 0.29 to 0.46 times the bound: **PASS**. In tokens per second they are 0.93 to 1.12 times it. That engine holds every expert in memory there, so the storage part of the arithmetic, the cache and hit-rate estimates and the first-token estimates were not compared with it. This program was given no measurement of an engine built to this design.

5. **3 quantities are not known and 2 are derived, not read from the model's files.** Not known: how unevenly the model uses its experts; attention state per token; context length the engine must offer. Derived: the size of `expert_weights` (derived); the size of `shared_weights` (derived). Section 8 says how each can be settled.


## 1. What the arithmetic presupposes of the engine, and which parts of the design have those node types

| Section | Node type | What the arithmetic assumes of it | Nodes of this design of that type |
|---|---|---|---|
| Storage | `model-conversion` | before the engine starts, writes the files the engine reads, every expert one contiguous range, while the published checkpoint is still on the same storage | `comp/muse/preparation` |
| Storage | `expert-source` | keeps every expert readable from storage for the whole run | `comp/muse/expert-source` |
| Memory plan | `memory-planning` | divides the budget among the weights every token uses, the attention state for the context, a staging area and a reserve, gives the expert cache the rest, and refuses to start below the smallest cache | `comp/muse/startup-memory-sizing` |
| Memory plan | `positional-state-store` | holds the attention state of every position up to the context length, in the same budget | `comp/muse/kv-store` |
| Memory plan | `expert-cache` | holds as many experts in memory as the plan leaves room for | `comp/muse/expert-cache` |
| Decode speed | `expert-cache` | holds the experts the residency policy keeps | `comp/muse/expert-cache` |
| Decode speed | `residency-policy` | keeps the most used experts of every layer in the cache | `comp/muse/cache-policy` |
| Decode speed | `expert-fetch` | reads a routed expert that is not cached from storage into a staging area before it is computed | `comp/muse/storage-reader` |
| Decode speed | `expert-dispatch` | issues the reads of a layer's missed experts before its cached experts are computed, so that reading and computing overlap fully | `comp/muse/expert-dispatch` |
| Time to first token | `prompt-reading` | reads a prompt in chunks, one layer at a time, reading each routed expert that is not cached once per chunk | `comp/muse/prompt-path` |
| Time to first token | `expert-fetch` | reads those experts from storage | `comp/muse/storage-reader` |
| Time to first token | `prefix-reuse` | is not used by the figures: they are for a prompt that shares no prefix with stored state. With a node of this type a request that continues a stored prefix reads only the rest | `comp/muse/resume-decision`, `comp/muse/parked-conversations` |
| What is not known | `telemetry` | records how often each expert is routed, which measures the unevenness of use on this engine | `comp/muse/engine-diagnostics`, `comp/muse/server-metrics` |

The nodes and their types are read from `examples/systems/muse/nodes.yaml`; a node's type is taken as that file states it. Every node's job there is the component's responsibility as the design now states it.

## 2. Quantities the arithmetic uses, and where each comes from

| Quantity | Value used | Comes from |
|---|---|---|
| Experts | 62 layers x 256 = 15,872; each token uses 8 per layer | model |
| All expert weights | 399.5 GB at 4 bits | model (derived) |
| Weights held in memory besides the experts | 8.5 GB | model (Section 3) |
| Memory budget | 80 GB of `mem0` | target (proposed) |
| Allocatable memory | 126.2 GB of `mem0`; nominal 128 GB | environment (measured) |
| Memory bandwidth | 273 GB/s | machine (vendor_stated) |
| Storage read rate | 4.75 GB/s with 8 reads in flight (one token routes 8 experts in a layer) and 4.82 GB/s, the best of the 4 rates measured, at 32 in flight, the largest concurrency tried; scattered ranges of one expert's size, measured with a test file and no engine running | environment (measured) |
| Storage capacity | 2015 GB, the total size of the file system as the environment reports it, not its free space | environment |
| Context length | 8,192, 32,768, 131,072 tokens | assumed by this program (the target sets none) |
| Model's maximum context | 1,000,000 tokens | model |
| Attention state per token | 0.25 MB and 2.03 MB: keys and values as wide as the hidden size (8,192) at 16 bits over 62 layers, and one eighth of that | assumed by this program: the model does not state it |
| Reserve left free | 2.0 GB | the design leaves this open (the design settles it in words only: `comp/muse/startup-memory-sizing`: "Memory left free for the operating system and for allocations not priced in advance."); assumed here: 2 GB |
| Smallest cache | 12.5 GB | the design leaves this open (the design settles it in words only: `comp/muse/startup-memory-sizing`: "The smallest cache the engine will start with: at least the experts one step can route, 8 times 62."); assumed here: the experts one step can route, 8 x 62 = 496, 12.5 GB |
| Staging area | 0.40 GB | the design leaves this open (no choice of `expert-fetch` names this quantity, so no decision of the design can give it); assumed here: 16 experts, twice what one token routes in a layer, 0.40 GB |
| Chunk of a prompt read at once | the whole prompt | the design leaves this open (the design settles it in words only: `comp/muse/prompt-path`: "Tokens per chunk. Larger chunks amortise each expert read over more tokens but need more experts in memory at once."); assumed here: the whole prompt as one chunk |
| Prompt lengths tabulated | 100, 1,000, 10,000 tokens | assumed by this program: the target's workload is not set |
| Range of unevenness of expert use (Zipf exponent) | 0, 0.45, 0.899 | assumed by this program. A choice, not a property of the model |
| Largest possible exponent | 0.899: above it the most used expert would be chosen more than once per token (8 different experts of 256 per token) | model (derived) |
| Speeds tabulated in Section 6 | 0.5, 1, 2, 5 tokens per second | assumed by this program |

## 3. What the model asks of the machine

One expert is 399.5 GB / (62 x 256) = 25.17 MB. The expert weights one token reads: 8 x 62 x 25.17 MB = 12.48 GB.

| Other weight | Size | Read by one token | Counted in the upper bound | Counted in the estimate |
|---|---|---|---|---|
| `shared_weights` (every weight other than the experts) | 8.50 GB | the part after those listed inside it | only the parts listed with a size | yes |
| `token_embedding` (inside `shared_weights`) | 0.83 GB (202,048 x 8,192 values at 4 bits, the bits of the expert weights: the model gives none for this table) | one row | yes | yes |
| `output_head_weights` (inside `shared_weights`) | 0.83 GB (202,048 x 8,192 values at 4 bits, the bits of the expert weights: the model gives none for this table) | all of it | yes | yes |
| `encoder_weights` (inside `shared_weights`) | not given | not for text input | no | inside the remainder |

Bytes one token reads at least, for one sequence and one token per pass: **13.31 GB**. As an estimate: 20.16 GB. Attention state read per token is not counted in either; it lowers the true speed, so leaving it out keeps the upper bound an upper bound.

- `shared_weights` (8.5 GB) holds every weight other than the experts: with the experts it makes up the model's 8.16e+11 parameters at 4 bits. Inside it, `encoder_weights` has no size in the description and is not read by every token of this target. The remainder of it after the parts with a size, 6.84 GB, is therefore counted in the estimate but not in the upper bound: the bytes a token reads may be higher than the bound's figure by up to that much, so the bound holds but may be loose by that much.
- `encoder_weights` is held in memory with `shared_weights` because the description gives it no size of its own; an engine for this target need not hold it, which would leave more memory for the cache.

The model description's own notes on the weights counted above. The program does not interpret them; where one says a size or the amount a token reads differs, the figures above do not reflect it:

- `expert_weights`: Assumes the 42B active parameters are all the non-expert parameters plus 8 of 256 experts per layer. Then experts E and the rest S satisfy E + S = 816B and E/32 + S = 42B, giving E = 799.0B and S = 17.0B. At 4 bits per parameter (NVFP4) the experts are 399.5 GB, about 25.2 MB each. The true value is in the weight file headers.
- `shared_weights`: 17.0B non-expert parameters under the same assumption, at 4 bits. It includes the embedding table and the output head. If these are kept at 16 bits the figure is 34 GB.
- `token_embedding`: 202,048 rows of 8,192 values: 1.66B parameters, counted inside shared_weights.
- `output_head_weights`: Counted inside shared_weights. Whether it is tied to the embedding table is not stated on the card.

## 4. Storage

The prepared files take 408 GB (all expert weights and the weights held besides them). The storage is 2015 GB, the total size of the file system as the environment reports it, not its free space.

| Published checkpoint | Size | How the size is known | Checkpoint and prepared files together | Fits |
|---|---|---|---|---|
| BF16 | 1632 GB | 8.16e+11 parameters at 16 bits | 2040 GB | **no** |
| NVFP4 | 408 GB | 8.16e+11 parameters at 4 bits | 816 GB | yes |

The target names no checkpoint; the row at the experts' own precision (NVFP4) decides the result. The other rows show what another checkpoint would need. Free space is not reported, so files already on the device are not counted.

**Result:** the checkpoint and the prepared files fit together.

## 5. Memory plan: how large the expert cache can be

The budget, 80 GB, minus the weights held besides the experts (8.5 GB), the attention state, the staging area (0.40 GB) and the reserve (2.0 GB) is the cache. A row fits when the cache is at least the smallest cache, 12.5 GB. The environment reports 126.2 GB allocatable in `mem0`; the budget is within it.

| Context (tokens) | Attention state per token | Attention state | Expert cache | Experts cached | Share of all experts |
|---|---|---|---|---|---|
| 8,192 | as wide as the hidden size, 2.03 MB | 16.6 GB | 52.5 GB | 2,084 | 13% |
| 8,192 | one eighth of that, 0.25 MB | 2.1 GB | 67.0 GB | 2,663 | 17% |
| 32,768 | as wide as the hidden size, 2.03 MB | 66.6 GB | **does not fit**: 10.0 GB short | — | — |
| 32,768 | one eighth of that, 0.25 MB | 8.3 GB | 60.8 GB | 2,415 | 15% |
| 131,072 | as wide as the hidden size, 2.03 MB | 266.3 GB | **does not fit**: 209.7 GB short | — | — |
| 131,072 | one eighth of that, 0.25 MB | 33.3 GB | 35.8 GB | 1,423 | 9% |

**Result:** 4 of 6 rows fit; the cache holds 9% to 17% of the experts in them, and the experts are 5.0 times the budget. Across the rows the attention state takes 2.1 GB to 266.3 GB from the same budget.

## 6. Decode speed

**Upper bound, with no assumption about how the experts are used:** 20.5 tokens per second. Memory bandwidth (273 GB/s) divided by the bytes one token reads at least (13.31 GB, Section 3), with every routed expert already in memory. It holds for one sequence and one token per pass over the weights; an engine that checks several drafted tokens in one pass can produce more tokens per second than this. It rests on the sizes of the weights as the model states them.

**Estimate with every weight in memory:** 13.5 tokens per second, with the bytes of the estimate (20.16 GB).

**Reference point, no expert in memory:** 0.39 tokens per second, every routed expert read from storage at 4.82 GB/s. Not a bound: a real engine with a cache is faster, and computation makes it slower.

**Estimates under stated assumptions.** Between these, the share of a token's experts found in the cache decides the speed. The estimates assume: (1) each token's choice of experts is independent of the previous token's; (2) the cache holds exactly the most used experts of every layer, which is the best a fixed set can do under (1); (3) reads overlap fully with computation, and computation itself takes no time beyond reading memory. Under (1) no cache can do better than (2). If successive tokens repeat experts, a cache that follows recent use finds more, so these estimates are **not** upper bounds on speed; (3) makes them optimistic. They are estimates, not bounds.

**Largest cache: 17% of experts cached** (context 8,192, attention state one eighth of that).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Estimate at 4.75 GB/s | Estimate at 4.82 GB/s |
|---|---|---|---|---|
| 0 (even) | 17% | 10.39 GB | 0.46 tok/s | 0.46 tok/s |
| 0.45 | 36% | 8.05 GB | 0.59 tok/s | 0.60 tok/s |
| 0.899 | 64% | 4.44 GB | 1.07 tok/s | 1.09 tok/s |

**Smallest cache: 9% of experts cached** (context 131,072, attention state one eighth of that).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Estimate at 4.75 GB/s | Estimate at 4.82 GB/s |
|---|---|---|---|---|
| 0 (even) | 9% | 11.37 GB | 0.42 tok/s | 0.42 tok/s |
| 0.45 | 24% | 9.45 GB | 0.50 tok/s | 0.51 tok/s |
| 0.899 | 54% | 5.80 GB | 0.82 tok/s | 0.83 tok/s |

**Result:** 0.42 to 1.09 tokens per second as estimates under the assumptions above. Holding the other factors, the estimate moves most with how unevenly the experts are used (up to 2.34 times), then the size of the cache, which the context length and the attention state set (up to 1.31 times), then the storage read rate (up to 1.01 times). Across the tabulated exponents, 0 to 0.899, the estimate for the largest cache at 4.82 GB/s goes from 0.46 to 1.09 tokens per second.

What a given speed requires, under the same assumptions:

| Speed | Share that must be found in cache at 4.75 GB/s | Share that must be found in cache at 4.82 GB/s |
|---|---|---|
| 0.5 tok/s | 24% | 23% |
| 1 tok/s | 62% | 61% |
| 2 tok/s | 81% | 81% |
| 5 tok/s | 92% | 92% |

0.5 tok/s is reached in 4 of 6 rows above at the best rate (lowest exponent among them: 0.45); 1 tok/s is reached in 1 of 6 rows above at the best rate (lowest exponent among them: 0.899); 2 tok/s is reached in no row above; 5 tok/s is reached in no row above.

## 7. Time to first token

A prompt is read as one chunk, one layer at a time, so an expert routed by several tokens of a chunk is read once. The table gives the bytes read from storage for a prompt that shares nothing with stored state, for the largest cache (17%), and the time that reading alone takes. Same assumptions as Section 6: tokens choose independently, so a prompt whose tokens repeat experts reads fewer; these are estimates, **not** lower bounds on time.

| Prompt (tokens) | Use of experts | Read from storage | Share of uncached experts read per chunk | Estimate at 4.75 GB/s | Estimate at 4.82 GB/s |
|---|---|---|---|---|---|
| 100 | 0 (even) | 319 GB | 96% | 67 s | 66 s |
| 100 | 0.899 | 231 GB | 69% | 49 s | 48 s |
| 1,000 | 0 (even) | 332 GB | 100% | 70 s | 69 s |
| 1,000 | 0.899 | 332 GB | 100% | 70 s | 69 s |
| 10,000 | 0 (even) | 332 GB | 100% | 70 s | 69 s |
| 10,000 | 0.899 | 332 GB | 100% | 70 s | 69 s |

**Result:** 48 to 70 seconds of storage reading before the first token, as estimates. Whatever the use of experts, one chunk reads each uncached expert at most once: at most 332 GB, 69 s at 4.82 GB/s per chunk. Nodes of type `prefix-reuse` in this design: `comp/muse/resume-decision`, `comp/muse/parked-conversations`; a request that continues a stored prefix reads only what follows it.

## 8. What is not known, and how to find out

| Unknown | Treated here as | How to settle it | Node type that would settle it in the engine | Nodes of this design |
|---|---|---|---|---|
| How unevenly the model uses its experts | Zipf exponents 0, 0.45, 0.899 | record routing over the benchmark's prompts on any machine that can run the model | `telemetry` | `comp/muse/engine-diagnostics`, `comp/muse/server-metrics` |
| Attention state per token | 0.25 MB and 2.03 MB: keys and values as wide as the hidden size (8,192) at 16 bits over 62 layers, and one eighth of that | read the model's config.json | `positional-state-store` | `comp/muse/kv-store` |
| Context length the engine must offer | tabulated for 8,192, 32,768, 131,072 tokens | a decision of the project, written into the target | `memory-planning` | `comp/muse/startup-memory-sizing` |

## 9. What the design records for the parts the arithmetic presupposes

Read from each node's component in the design: its decisions (with a value where one is given) and invariants, and the choices of the node type the node settles. None of these changes a figure unless Section 2 says so.

- `model-conversion`, `comp/muse/preparation`: the design records no decision, invariant or settled choice for this node.
- `expert-source`, `comp/muse/expert-source`: decisions: `read-mode`: Whether reads bypass the operating system's page cache. Bypassing keeps the page cache from taking memory the budget does not count | `read-concurrency`: How many expert reads may be in flight at once; invariants: `inv/whole-expert`: A delivered expert is complete; a short read is an error, never a partly filled buffer reported as ready.
- `memory-planning`, `comp/muse/startup-memory-sizing`: decisions: `memory-budget`: The total the engine may hold in the unified pool. Fixed by the request | `reserve`: Memory left free for the operating system and for allocations not priced in advance | `context-length`: The longest context the engine offers. With the attention state's size per token it sets how much memory the cache loses | `min-cache`: The smallest cache the engine will start with: at least the experts one step can route, 8 times 62 | `reserve-recheck`: After allocating, read free memory again and shrink the cache if the reserve was not really left; settles: the reserve left free: Memory left free for the operating system and for allocations not priced in advance | the least a cache may be and still work: The smallest cache the engine will start with: at least the experts one step can route, 8 times 62.
- `positional-state-store`, `comp/muse/kv-store`: the design records no decision, invariant or settled choice for this node.
- `expert-cache`, `comp/muse/expert-cache`: decisions: `slot-count`: How many slots the cache has. Decided at startup from the memory budget; see startup memory sizing; invariants: `inv/read-ready`: A slot is reported as holding an expert only after that expert's bytes have fully arrived | `inv/no-overwrite-while-read`: A slot is not written while any launched computation may still read it.
- `residency-policy`, `comp/muse/cache-policy`: decisions: `admit-rule`: The condition under which a missed expert enters the cache: always, or only when its usage count exceeds that of the least used resident expert of the layer | `decay`: How fast usage counts fade | `per-layer-share`: Whether every layer has the same number of slots or slots move to the layers with the most misses | `starting-contents`: What the cache holds before any request: nothing, or the experts a recorded usage profile ranks highest; invariants: `inv/read-ready`: An entering expert is marked resident only after its bytes have fully arrived | `inv/no-overwrite-while-read`: A slot is not overwritten while a computation that may read it is in progress; settles: how use counts age, so that recent use outweighs old use: How fast usage counts fade.
- `expert-fetch`, `comp/muse/storage-reader`: invariants: `inv/ordered-read`: A read is complete before the computation that uses its destination starts.
- `expert-dispatch`, `comp/muse/expert-dispatch`: decisions: `wait-or-stage`: Whether a missed expert is computed from the staging area and then dropped, or is computed after the cache policy has admitted it to the cache; invariants: `inv/always-served`: Every routed expert is computed exactly once in the step that routed it | `inv/reads-first`: The reads of a layer's missed experts are issued before the layer's cached experts are computed, so the two overlap.
- `prompt-reading`, `comp/muse/prompt-path`: decisions: `chunk-size`: Tokens per chunk. Larger chunks amortise each expert read over more tokens but need more experts in memory at once | `borrow-cache`: Whether the prompt path may use cache slots for a layer's experts while it reads, and whether it restores the cache afterwards | `feeds-usage`: Whether the experts a prompt routes count toward the usage that decides the cache's contents for generation; settles: chunk size: Tokens per chunk. Larger chunks amortise each expert read over more tokens but need more experts in memory at once.
- `prefix-reuse`, `comp/muse/resume-decision`: the design records no decision, invariant or settled choice for this node.
- `prefix-reuse`, `comp/muse/parked-conversations`: the design records no decision, invariant or settled choice for this node.
- `telemetry`, `comp/muse/engine-diagnostics`: the design records no decision, invariant or settled choice for this node.
- `telemetry`, `comp/muse/server-metrics`: the design records no decision, invariant or settled choice for this node.

## 10. Changes that would move the figures

Each change alters one quantity of the arithmetic. The levels are every level the node type lists for its own work (how far it can move the output); which one a given change reaches depends on how it is made.

| Change | Quantity it alters | Node type | Nodes of this design | Levels the type lists | Allowed by the target |
|---|---|---|---|---|---|
| Fewer bytes per expert: the expert weights stored at a lower precision | bytes per expert | `model-conversion` | `comp/muse/preparation` | `bit_exact`, `numeric`, `distribution_exact`, `approximate`, `defines` | not decided: the target's `allowed_transformations` is not set |
| Fewer experts computed per token: low-ranked routed experts that are not cached are omitted | experts read per token | `expert-dispatch` | `comp/muse/expert-dispatch` | `bit_exact`, `numeric`, `approximate` | not decided: the target's `allowed_transformations` is not set |
| More than one token per pass over the weights: drafted tokens checked in one pass | tokens per pass | `draft-proposal` | none | `bit_exact`, `numeric`, `distribution_exact`, `approximate` | not decided: the target's `allowed_transformations` is not set |
| More than one token per pass over the weights: drafted tokens checked in one pass | tokens per pass | `draft-verification` | none | `bit_exact`, `numeric`, `distribution_exact`, `approximate` | not decided: the target's `allowed_transformations` is not set |

## 11. Summary

- **Can it run?** **Yes** on memory and storage for the rows of Section 5 that fit. Open: the target sets no context length; the contexts that fit here are 8,192, 32,768, 131,072 (not every attention-state case).
- **Can the model be held in memory?** No: the experts are 400 GB, and the cache holds at most 17% of them.
- **Upper bound on decode speed:** 20.5 tokens per second (one sequence, one token per pass). Estimate with every weight in memory: 13.5. Reference with no expert in memory: 0.39.
- **Estimated decode speed** under the assumptions of Section 6: 0.42 to 1.09 tokens per second.
- **Estimated storage time before the first token** for prompts of 100, 1,000, 10,000 tokens: 48 to 70 seconds.
- **Largest spread in this run:** how unevenly the experts are used, up to 2.34 times.
- **What the project still has to decide:** the target has 12 blocking gaps; run `python tools/so_check.py check spec/muse-spark-open-on-dgx-spark/target` for the list.
