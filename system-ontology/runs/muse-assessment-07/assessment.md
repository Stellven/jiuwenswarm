# Bounds and estimates for `model/muse-spark-open` on `hw/dgx-spark` within the target's 80 GB budget, for an engine that keeps part of the experts in memory

Model `model/muse-spark-open` · machine `hw/dgx-spark` · environment `env/dgx-spark-measured-20261119` · target `spec/muse-spark-open-on-dgx-spark/target` · design `sys/muse-on-spark` (node types only) · node types draft 0.9.

**The model is not the one the target names.** The target names `model/muse-spark-open-ud-iq2-xxs`; these figures are for `model/muse-spark-open`, given on the command line. Structure figures are from Meta's model card (https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B) and release post (https://research.meta.ai/blog/muse-spark-open), read 2026-11-10. config.json needs a login and was not read. On 2026-11-19 the headers of the model files that are on the DGX Spark were read (a third party's conversion to GGUF, about 2 bits per expert weight): they give the parameter count of every tensor and the attention dimensions, and the sizes below are those counts at 4 bits. The published files themselves were not read. The card mentions no draft head, no always-on shared expert and no state other than attention; the files have none either. Whether the target allows this model in place of its own is the target's to say; this program does not judge it.

**What is assessed.** The figures are bounds and estimates for the model `model/muse-spark-open` on the machine `hw/dgx-spark` within the target's memory budget of 80 GB, for an engine of one architecture: the weights every token uses and part of the experts kept in memory, the rest read from storage when routed. The design `sys/muse-on-spark` contributes which node types it has and nothing else numeric: no figure changes when the design's decisions change, unless a decision gives a number this program reads (memory-planning: the reserve left free, memory-planning: the least a cache may be and still work, prompt-reading: chunk size; Section 2). In this run no decision of the design gave a number. This is not an assessment of the design's quality.

## Read this first: what these figures can and cannot say

0. **What they are about:** the model, the machine and the target's budget, for an engine that keeps the weights every token uses and part of the experts in memory and reads the rest from storage when routed. The design gives only which node types it has, and no number. No figure changes when its decisions change unless a decision gives a number this program reads. This is not an assessment of the design's quality.

1. **One figure is an upper bound that needs no assumption about how the experts are used:** 12.3 tokens per second, memory bandwidth over the bytes a token surely reads, for one sequence and one token per pass, with the weight sizes as the model states them (Section 2 says how each is known). With no expert in memory a token takes 2.6 s (0.38 tokens per second), a reference point, not a bound.

2. **Every other speed and time is an estimate under stated assumptions** (Section 6): each token's choice of experts independent of the previous token's, the cache holding the most used experts, reading fully overlapped and computation not counted. If successive tokens repeat experts, a cache that follows recent use finds more: the speed estimates are then not upper bounds and the first-token estimates not lower bounds.

3. **The figures are for the target's budget of 80 GB** (one of 2 candidates the target names and has not chosen among: 128 GB (kickoff page: the target, a working set of 128 GB of unified memory); 80 GB (kickoff page: the reference configuration of Strata on DGX Spark, 80 GB of unified memory)); the environment reports 127.2 GB allocatable. They change with the budget, the reserve, the context lengths and the range of unevenness, each listed with its source in Section 2.

4. **Back-test** (`runs/strata-backtest-02`): the memory-bandwidth upper bound, computed the same way, was compared with the speeds the project of `sys/strata` reports for model `model/qwen3.8-flash-125b-a6b` on the same machine description as here. Condition: every reported speed / fewest tokens per pass <= bound (written 2026-11-18, after the first result was known). Per pass the reported speeds are 0.29 to 0.46 times the bound: **PASS**. In tokens per second they are 0.93 to 1.12 times it. That engine holds every expert in memory there, so the storage part of the arithmetic, the cache and hit-rate estimates and the first-token estimates were not compared with it. This program was given no measurement of an engine built to this design.

5. **2 quantities are not known and 3 are derived, not read from the model's files.** Not known: how unevenly the model uses its experts; context length the engine must offer. Derived: the size of `expert_weights` (derived); the size of `shared_weights` (derived); the size of `output_head_weights` (derived). Section 8 says how each can be settled.


## 1. What the arithmetic presupposes of the engine, and which parts of the design have those node types

| Section | Node type | What the arithmetic assumes of it | Nodes of this design of that type |
|---|---|---|---|
| Storage | `model-conversion` | before the engine starts, writes the files the engine reads, every expert one contiguous range, while the checkpoint they are made from is still on the same storage | `comp/muse/preparation` |
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
| All expert weights | 399.4 GB at 4 bits | model (derived) |
| Weights held in memory besides the experts | 10.6 GB | model (Section 3) |
| Memory budget | 80 GB of `mem0` | target (one of 2 candidates the target names and has not chosen among: 128 GB (kickoff page: the target, a working set of 128 GB of unified memory); 80 GB (kickoff page: the reference configuration of Strata on DGX Spark, 80 GB of unified memory)) |
| Allocatable memory | 127.2 GB of `mem0`; nominal 128 GB | environment (measured) |
| Memory bandwidth | 273 GB/s | machine (vendor_stated) |
| Storage read rate | 4.77 GB/s with 8 reads in flight (one token routes 8 experts in a layer) and 4.77 GB/s, the best of the 4 rates measured, at 8 in flight (the largest tried was 32); scattered ranges of 25.2 MB each, the size of one expert here, measured with a test file and no engine running | environment (measured) |
| Storage capacity | 2015 GB, the total size of the file system as the environment reports it, not its free space | environment |
| Context length | 8,192, 32,768, 131,072 tokens | assumed by this program (the target sets none) |
| Model's maximum context | 1,000,000 tokens | model |
| Attention state per token | 0.254 MB with every layer keeping every token; 46 of the 62 layers attend only to the last 2,048 tokens and need the state of no more than those | model |
| Reserve left free | 2.0 GB | the design leaves this open (the design settles it in words only: `comp/muse/startup-memory-sizing`: "Memory left free for the operating system and for allocations not priced in advance."); assumed here: 2 GB |
| Smallest cache | 12.5 GB | the design leaves this open (the design settles it in words only: `comp/muse/startup-memory-sizing`: "The smallest cache the engine will start with: at least the experts one step can route, 8 times 62."); assumed here: the experts one step can route, 8 x 62 = 496, 12.5 GB |
| Staging area | 0.40 GB | the design leaves this open (no choice of `expert-fetch` names this quantity, so no decision of the design can give it); assumed here: 16 experts, twice what one token routes in a layer, 0.40 GB |
| Chunk of a prompt read at once | the whole prompt | the design leaves this open (the design settles it in words only: `comp/muse/prompt-path`: "Tokens per chunk. Larger chunks amortise each expert read over more tokens but need more experts in memory at once."); assumed here: the whole prompt as one chunk |
| Prompt lengths tabulated | 100, 1,000, 10,000 tokens | assumed by this program: it does not read prompt lengths from the target's workload |
| Range of unevenness of expert use (Zipf exponent) | 0, 0.45, 0.899 | assumed by this program. A choice, not a property of the model |
| Largest possible exponent | 0.899: above it the most used expert would be chosen more than once per token (8 different experts of 256 per token) | model (derived) |
| Speeds tabulated in Section 6 | 0.5, 1, 2, 5 tokens per second | assumed by this program |

## 3. What the model asks of the machine

One expert is 399.4 GB / (62 x 256) = 25.17 MB. The expert weights one token reads: 8 x 62 x 25.17 MB = 12.48 GB.

| Other weight | Size | Read by one token | Counted in the upper bound | Counted in the estimate |
|---|---|---|---|---|
| `shared_weights` | 8.91 GB | all of it | yes | yes |
| `token_embedding` | 0.83 GB | one row | yes | yes |
| `output_head_weights` | 0.83 GB | all of it | yes | yes |
| `encoder_weights` | not given | not for text input | no | no |

Bytes one token reads at least, for one sequence and one token per pass: **22.22 GB**. As an estimate: 22.22 GB. Attention state read per token is not counted in either; it lowers the true speed, so leaving it out keeps the upper bound an upper bound.

The model description's own notes on the weights counted above. The program does not interpret them; where one says a size or the amount a token reads differs, the figures above do not reflect it:

- `expert_weights`: 798,863,917,056 parameters at 4 bits: in each of 62 layers three tensors of 4,096 x 4,096 x 256. One expert is 3 x 4,096 x 4,096 parameters, 25.17 MB at 4 bits. The experts work in a latent space of width 4,096, not at the hidden size.
- `shared_weights`: 17,817,304,320 parameters at 4 bits: every weight a token reads in full besides the experts and the two vocabulary tables listed below. Attention 13.52B, the projections into and out of the experts' latent space 4.16B, the router 0.13B, norms. In the conversion read on the Spark these tensors are stored at 6 to 8 bits and take 17.3 GB.
- `token_embedding`: 1,655,177,216 parameters at 4 bits: 202,048 rows of 8,192 values. A token reads one row.
- `output_head_weights`: 1,655,177,216 parameters at 4 bits. A tensor of its own in the files: it is not tied to the embedding table.

## 4. Storage

The prepared files take 410 GB (all expert weights and the weights held besides them). The storage is 2015 GB, the total size of the file system as the environment reports it, not its free space.

| Checkpoint | Size | How the size is known | Checkpoint and prepared files together | Fits |
|---|---|---|---|---|
| Muse-Spark-Open-816B-A42B, Unsloth UD-IQ2_XXS conversion to GGUF: six files, 225.6 GB, pinned by hash | 226 GB | taken as the weights of the target's model, `model/muse-spark-open-ud-iq2-xxs`, as its description sizes them; no field of the target gives the checkpoint a size | 636 GB | yes |

The target names the checkpoint: Muse-Spark-Open-816B-A42B, Unsloth UD-IQ2_XXS conversion to GGUF: six files, 225.6 GB, pinned by hash. Free space is not reported, so files already on the device are not counted.

**Result:** the checkpoint and the prepared files fit together.

## 5. Memory plan: how large the expert cache can be

The budget, 80 GB, minus the weights held besides the experts (10.6 GB), the attention state, the staging area (0.40 GB) and the reserve (2.0 GB) is the cache. A row fits when the cache is at least the smallest cache, 12.5 GB. The environment reports 127.2 GB allocatable in `mem0`; the budget is within it.

| Context (tokens) | Attention state per token | Attention state | Expert cache | Experts cached | Share of all experts |
|---|---|---|---|---|---|
| 8,192 | every layer keeps every token, 0.25 MB | 2.1 GB | 64.9 GB | 2,581 | 16% |
| 8,192 | the 46 windowed layers keep their last 2,048 tokens only, 0.25 MB | 0.9 GB | 66.1 GB | 2,627 | 17% |
| 32,768 | every layer keeps every token, 0.25 MB | 8.3 GB | 58.7 GB | 2,333 | 15% |
| 32,768 | the 46 windowed layers keep their last 2,048 tokens only, 0.25 MB | 2.5 GB | 64.5 GB | 2,563 | 16% |
| 131,072 | every layer keeps every token, 0.25 MB | 33.3 GB | 33.7 GB | 1,341 | 8% |
| 131,072 | the 46 windowed layers keep their last 2,048 tokens only, 0.25 MB | 9.0 GB | 58.1 GB | 2,307 | 15% |

**Result:** 6 of 6 rows fit; the cache holds 8% to 17% of the experts in them, and the experts are 5.0 times the budget. Across the rows the attention state takes 0.9 GB to 33.3 GB from the same budget.

## 6. Decode speed

**Upper bound, with no assumption about how the experts are used:** 12.3 tokens per second. Memory bandwidth (273 GB/s) divided by the bytes one token reads at least (22.22 GB, Section 3), with every routed expert already in memory. It holds for one sequence and one token per pass over the weights; an engine that checks several drafted tokens in one pass can produce more tokens per second than this. It rests on the sizes of the weights as the model states them.

**Estimate with every weight in memory:** 12.3 tokens per second, with the bytes of the estimate (22.22 GB).

**Reference point, no expert in memory:** 0.38 tokens per second, every routed expert read from storage at 4.77 GB/s. Not a bound: a real engine with a cache is faster, and computation makes it slower.

**Estimates under stated assumptions.** Between these, the share of a token's experts found in the cache decides the speed. The estimates assume: (1) each token's choice of experts is independent of the previous token's; (2) the cache holds exactly the most used experts of every layer, which is the best a fixed set can do under (1); (3) reads overlap fully with computation, and computation itself takes no time beyond reading memory. Under (1) no cache can do better than (2). If successive tokens repeat experts, a cache that follows recent use finds more, so these estimates are **not** upper bounds on speed; (3) makes them optimistic. They are estimates, not bounds.

**Largest cache: 17% of experts cached** (context 8,192, attention state the 46 windowed layers keep their last 2,048 tokens only).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Estimate at 4.77 GB/s |
|---|---|---|---|
| 0 (even) | 17% | 10.42 GB | 0.46 tok/s |
| 0.45 | 35% | 8.09 GB | 0.59 tok/s |
| 0.899 | 64% | 4.47 GB | 1.07 tok/s |

**Smallest cache: 8% of experts cached** (context 131,072, attention state every layer keeps every token).

| Use of experts (Zipf exponent) | Found in cache | Read from storage per token | Estimate at 4.77 GB/s |
|---|---|---|---|
| 0 (even) | 8% | 11.43 GB | 0.42 tok/s |
| 0.45 | 23% | 9.56 GB | 0.50 tok/s |
| 0.899 | 53% | 5.93 GB | 0.81 tok/s |

**Result:** 0.42 to 1.07 tokens per second as estimates under the assumptions above. Holding the other factors, the estimate moves most with how unevenly the experts are used (up to 2.33 times), then the size of the cache, which the context length and the attention state set (up to 1.33 times). Fixed in this run: the storage read rate. Across the tabulated exponents, 0 to 0.899, the estimate for the largest cache at 4.77 GB/s goes from 0.46 to 1.07 tokens per second.

What a given speed requires, under the same assumptions:

| Speed | Share that must be found in cache at 4.77 GB/s |
|---|---|
| 0.5 tok/s | 24% |
| 1 tok/s | 62% |
| 2 tok/s | 81% |
| 5 tok/s | 92% |

0.5 tok/s is reached in 3 of 6 rows above at the best rate (lowest exponent among them: 0.45); 1 tok/s is reached in 1 of 6 rows above at the best rate (lowest exponent among them: 0.899); 2 tok/s is reached in no row above; 5 tok/s is reached in no row above.

## 7. Time to first token

A prompt is read as one chunk, one layer at a time, so an expert routed by several tokens of a chunk is read once. The table gives the bytes read from storage for a prompt that shares nothing with stored state, for the largest cache (17%), and the time that reading alone takes. Same assumptions as Section 6: tokens choose independently, so a prompt whose tokens repeat experts reads fewer; these are estimates, **not** lower bounds on time.

| Prompt (tokens) | Use of experts | Read from storage | Share of uncached experts read per chunk | Estimate at 4.77 GB/s |
|---|---|---|---|---|
| 100 | 0 (even) | 319 GB | 96% | 67 s |
| 100 | 0.899 | 232 GB | 69% | 49 s |
| 1,000 | 0 (even) | 333 GB | 100% | 70 s |
| 1,000 | 0.899 | 333 GB | 100% | 70 s |
| 10,000 | 0 (even) | 333 GB | 100% | 70 s |
| 10,000 | 0.899 | 333 GB | 100% | 70 s |

**Result:** 49 to 70 seconds of storage reading before the first token, as estimates. Whatever the use of experts, one chunk reads each uncached expert at most once: at most 333 GB, 70 s at 4.77 GB/s per chunk. Nodes of type `prefix-reuse` in this design: `comp/muse/resume-decision`, `comp/muse/parked-conversations`; a request that continues a stored prefix reads only what follows it.

## 8. What is not known, and how to find out

| Unknown | Treated here as | How to settle it | Node type that would settle it in the engine | Nodes of this design |
|---|---|---|---|---|
| How unevenly the model uses its experts | Zipf exponents 0, 0.45, 0.899 | record routing over the benchmark's prompts on any machine that can run the model | `telemetry` | `comp/muse/engine-diagnostics`, `comp/muse/server-metrics` |
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

- **Can it run?** **Yes** on memory and storage for the rows of Section 5 that fit. Open: the target sets no context length; the contexts that fit here are 8,192, 32,768, 131,072.
- **Can the model be held in memory?** No: the experts are 399 GB, and the cache holds at most 17% of them.
- **Upper bound on decode speed:** 12.3 tokens per second (one sequence, one token per pass). Estimate with every weight in memory: 12.3. Reference with no expert in memory: 0.38.
- **Estimated decode speed** under the assumptions of Section 6: 0.42 to 1.07 tokens per second.
- **Estimated storage time before the first token** for prompts of 100, 1,000, 10,000 tokens: 49 to 70 seconds.
- **Largest spread in this run:** how unevenly the experts are used, up to 2.33 times.
- **What the project still has to decide:** the target has 7 blocking gaps; run `python tools/so_check.py check spec/muse-spark-open-on-dgx-spark/target` for the list.
