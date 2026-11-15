# Research methodology CC starter kit for RSI

Seven new self-contained job packages implement 24 native capabilities. They
contain executable components, agent skills, methods, source provenance, examples
and verification units. They are CPU reference prototypes, not already-integrated
Strata optimizations or GPU performance certificates. No inference-engine source,
model format or production default was changed in this build.

| CC | Implemented capabilities and components | Research families |
| --- | --- | --- |
| `engine.expert_cache_lab` | Trace validation; byte-bounded LRU/LFU/density-hybrid replay; causal whole-token/layer expert-set prediction and frozen request holdout | MoE-Infinity, DwarfStar, moe-offload, InferSSD, LayerStoRm |
| `engine.ssd_streaming_lab` | Coalescing planner; explicit I/O cost model; actual bounded asynchronous positional reads with cancellation, byte/count backpressure and short-read checks | SSD expert streaming and overlap |
| `engine.heterogeneous_placement_lab` | Shared-memory-aware placement from measured costs; actual selected-expert CPU projection/reduction oracle; overlap simulation | KTransformers, Fiddler, LiteMoE, FlexGen, ZeRO-Inference, AirLLM |
| `engine.precision_lab` | Actual signed INT4 pack/unpack reference; numerical error checks; block calibration; separate weight/KV size planning | llama.cpp/GGML, ExLlamaV2, precision-aware offload |
| `engine.kv_reuse_lab` | Full-identity prefix matching; reference-counted pages and copy-on-write; MHA/MLA-aware storage estimates; executable invariants | vLLM, SGLang, llama.cpp, DwarfStar, Strata |
| `engine.serving_scheduler_lab` | Bounded token-budget/chunked-prefill scheduler; decode priority with prefill reserve; trace analysis and matched-workload comparisons | PagedAttention/RadixAttention serving and batch scheduling |
| `factory.methodology_transfer_lab` | Source/target assumption checks; one-variable cheap-first trial recipes; phase-separated matched ABBA arithmetic | Research intake, ablation, reproducible workload measurement |

Every package can be sealed/imported and used on its own. A node may combine
packages when the task benefits, but no pair requires interlaced execution to be
useful. `EXAMPLES.json` maps each capability to complete native Host inputs.
`SKILL.md` explains when to use the tools and what evidence should trigger a lab
run. `VERIFICATION-UNITS.json` attaches local executable checks. Local checks are
not registered as generic factory `cc_qualification` admission checkers and do not
grant execution authority.

## Concrete implementation directions

1. **Expert-set prefetch:** collect request/token/layer routing sets; compare
   frozen frequency and causal transition predictions without observing any
   current-set labels. Replay cache capacity, then port a selected policy into
   Strata's expert readiness path. Preserve every selected expert and coefficient;
   prediction only changes scheduling. Count useful-ready hits, late reads,
   wasted bytes and eviction stalls before measuring complete requests.
2. **Bounded SSD read queue:** use the actual positional-read component to test
   offsets, coalescing and backpressure on owned fixtures. Port the queue interface
   into a native reader, keeping buffers alive through GPU completion. POSIX reads
   already running are not interruptible; cancellation makes results unusable and
   shutdown joins workers. Completed result memory remains caller-owned.
3. **Compute where weights reside:** supply target-measured CPU/GPU operation
   and transfer costs to the placement component. Compare CPU expert execution
   plus activation transfer with weight transfer plus GPU execution. On Spark,
   CPU and GPU allocations consume one physical-memory budget. The CPU oracle is
   a projection/reduction, not a complete MoE MLP or a CUDA dispatch replacement.
4. **Prefix reuse and paged state:** test model/tokenizer/adapter/position/dtype/
   tenant identity, page sharing and copy-on-write before binding real KV tensors.
   DeepSeek compressed attention state needs the actual MLA layout. Serving
   policies need measured operation costs before their discrete tick estimates
   can predict latency.
5. **Precision experiments:** calibrate blocks and run reference error checks
   before writing a format/kernel adapter. The bundled INT4 codec is an explicit
   custom reference format, not GGUF, EXL2 or Strata's existing packed layout.
   Weight quantization and quantized KV are separate approximation experiments;
   neither inherits semantic correctness from a small tensor test.

PowerInfer's activation assumptions and PowerInfer-2's mobile execution topology
are recorded as applicability constraints, not promised GB10 implementations.
AdapMoE-style expert skipping belongs to an explicitly approximate lane. Preserve
the exact/full-routing lane for scheduling and placement comparisons.

## A practical RSI cycle

An agent receives a task such as “reduce decode expert-wait time while retaining
all six selected experts.” It can use the cache package to establish a trace
baseline and one alternative, then choose whether to improve prediction or I/O.
The agent—not a static package graph—chooses the next change. A passing trace test
justifies a small native component test; it does not justify a speedup claim.
After integration, the builder uses the native ARM64 environment and the lab
quiets factory activity during measurement. Raw evidence and failed attempts are
retained. The agent evaluates the report, rejects ineffective candidates, and
records the next bounded hypothesis under the remaining budget.

RSI can separately improve the CC's job: input usability, missing-data handling,
runtime cost, precision, useful recommendations and integration success. Keep
versioned examples and independent verification cases as holdouts. Do not reward
only a simulated hit rate or a string labeled “passed.”

## Quick verification and import

From an existing factory checkout with its pinned Python environment:

```sh
python deploy/spark/qualify-research-ccs.py --output /absolute/new/receipt-directory
```

The finite runner seals these seven packages, runs their local CPU verifiers and
invokes every declared capability through the real CC Host. It saves release IDs,
source hashes, per-capability receipts and elapsed times. It performs no model,
GPU, network or build operation. A fresh output directory prevents overwriting
prior qualification evidence. The kit's evidence summary reports what actually
passed; do not infer model support or performance from the release seal.

For a single package, inspect its example inputs, prepare it with `Host.prepare`,
and call its chosen capability with `process.exec` in the existing session grants.
The supplied native tools use standard-library Python and inline JSON. The real
I/O example creates only an owned temporary fixture, not arbitrary filesystem
reads. Native CC execution remains trusted-local, not a sandbox boundary.

## Provenance and limits

Each SOURCES.json records verified primary repositories, revisions, licensing and
applicability notes. No upstream implementation was copied into these reference
components. Repository names alone are insufficient: `ro99/strata` and
`mehbul/strata` have different architectures, and DwarfStar's canonical reference
here is `antirez/ds4`; its inspected fork is labeled separately. LiteMoE identities
are also disambiguated. See RESEARCH-CACHE-IO.md, RESEARCH-PLACEMENT-PRECISION.md and
RESEARCH-KV-SERVING.md for source-to-method mappings and limitations.

The prior measured work found no robust general Strata speedup. This kit does not
relabel those results. It supplies implementable hypotheses and cheaper ways to
test components before another expensive inference experiment.

## Recorded quick checks

The final focused suite passed **59 tests in 11.86 seconds**, including catalog
discovery and real Host invocation. The separate package runner passed all seven
local verification scripts and **24 native capability examples**. Its external
release-bound receipts are in `research-cc-qualification-001/`; these are CPU-only
evidence, not production admission. Catalog discovery now finds 32 top-level
packages plus eight nested components (40 entries).
