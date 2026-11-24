# System Ontology: worked examples

Real excerpts from the description files, with a short note on how to read each. Everything here is checked by
`tools/so_check.py`. Full files are under `examples/`; every field is defined in `ontology/schema-reference.md` and
every term in `ontology/dictionary.md`.

The ontology has two description levels and one per-machine record:

| What | File kind | Example below |
|---|---|---|
| System level: the engine as a whole | `system` | Section 1 |
| Node level: one component, true on every machine | `component` | Section 2 |
| One engine on one machine | `engine_spec` | Section 3 |
| A new engine derived from an existing one | `component` with `derived_from` | Section 4 |
| A requirement | inside `engine_spec` | Section 5 |

## 1. System level: Strata as a whole

Excerpt of `examples/systems/strata/system.yaml`. The full file lists 100 flows; three are shown.

```yaml
kind: system
id: sys/strata
title: Strata
summary: Strata is an engine written for one mixture-of-experts model whose expert weights do not fit the fast memory
  of a consumer machine. Each token uses 10 of 512 experts in each of 48 layers. The engine keeps the weights every
  token needs and the most used experts in fast memory, keeps every expert in slow memory where the CPU computes
  the ones that are not in fast memory, moves experts between the two as usage changes, reads a lookup table from
  storage a few rows per token, and has the full model check several drafted tokens in one pass. A serving layer
  in front of the engine process holds conversations so that a continued conversation is not read again.
product:
  name: Strata
  revision: 504b143342a9fe1aa8320a7b31e11f5c0ac265c3
  upstream: https://github.com/Niko1221/Strata
  form: Written from scratch in C++ and CUDA, with a Python serving layer that drives the engine process.
targets:
- model: model/qwen3.8-flash-125b-a6b
  hardware: hw/pc-12g-64g
  spec: spec/qwen-flash-on-pc/strata-like
  note: A discrete GPU with 12 GB of its own memory and 64 GB of host memory. The configuration the component descriptions
    were read for.
- model: model/qwen3.8-flash-125b-a6b
  hardware: hw/dgx-spark
  spec: spec/qwen-flash-on-dgx-spark/strata-like
  note: One memory pool shared by CPU and GPU. Described from the project's document for this machine and from the
    code paths it names; nothing was run there.
components:
- comp/strata/setup
- comp/strata/loading
- comp/strata/serving
- comp/strata/conversation-reuse
- comp/strata/prompt-path
- comp/strata/token-path
- comp/strata/expert-subsystem
- comp/strata/speculation
- comp/strata/telemetry
mechanisms:
- mech/hot-expert-residency
- mech/work-based-prefill-split
- mech/draft-then-verify
- mech/route-tail-skip
flows:
- id: expert-usage
  sender: comp/strata/expert-dispatch
  receiver: comp/strata/adaptive-tier
  carries:
    content: signal
    refs:
    - expert_heat
  timing: per_layer
  description: How many tokens of the window routed each expert
- id: swap-requests
  sender: comp/strata/adaptive-tier
  receiver: comp/strata/host-to-device-transfer
  carries:
    content: control
    refs:
    - pending_swaps
  timing: background
  description: Experts to copy into the slots of experts that are leaving the cache
- id: residency-updates
  sender: comp/strata/adaptive-tier
  receiver: comp/strata/expert-cache
  carries:
    content: engine_state
    refs:
    - residency_table
  timing: background
  description: A leaving expert is marked absent before its slot is overwritten; an entering expert is marked resident
    after its copy lands
```

How to read it:

- `targets` names the model and hardware descriptions this engine is described for, and the engine spec for each.
- `components` lists only the top level. Each has its own file, and a subsystem lists its `parts` there.
- A flow is declared once, here, with who sends, who receives, what it carries and when. A component's inputs and
  outputs are the flows that name it. `refs` must be a state, data or operation that exists.
- `mechanisms` points to reusable optimisation hypotheses kept in separate files.

## 2. Node level: one component

`comp/strata/adaptive-tier`, verbatim from `examples/systems/strata/components-expert.yaml`.

```yaml
kind: component
id: comp/strata/adaptive-tier
system: sys/strata
parent: comp/strata/expert-subsystem
title: "Adaptive tier"
role: policy_runner
responsibility: "Keep the expert cache filled with the experts the current conversation uses most, by swapping a bounded number of them at fixed intervals."
not_responsible_for:
  - "The size of the cache"
  - "Where a missed expert is computed in the current window"
runs: [background]
state:
  owns: [expert_heat, pending_swaps]
  reads: [residency_table]
  writes: [residency_table]
needs_resources:
  - {resource: cpu, purpose: "choosing swaps, on a thread beside the commit and the next draft"}
policies: [expert-cache]
decisions:
  - {id: interval, text: "Run once every this many verify windows.", value: {value: 4, status: reported, source: "src/program/generate.cpp:887"}, resolved_at: design}
  - {id: max-swaps, text: "At most this many swaps per run, taken in order of gain across all layers.", value: {value: 96, status: reported, source: "src/program/generate.cpp:923"}, resolved_at: design}
  - {id: decay, text: "After each run every usage count is multiplied by this.", value: {value: 0.7, status: reported, source: "src/program/generate.cpp:892"}, resolved_at: design}
  - {id: min-gain, text: "A swap is made only if the entering expert's count exceeds the leaving expert's by at least this.", value: {value: 1.5, status: reported, source: "src/program/generate.cpp:895"}, resolved_at: design}
  - {id: min-usage, text: "An expert is a candidate to enter only if its count is at least this.", value: {value: 2, status: reported, source: "src/program/generate.cpp:13158"}, resolved_at: design}
invariants:
  - {id: inv/read-ready, text: "An entering expert is marked resident only after its copy has landed."}
  - {id: inv/no-overwrite-while-read, text: "A leaving expert is marked absent first; the copy into its slot waits until all work launched before that has completed."}
  - {id: inv/one-batch-in-flight, text: "A run does nothing while the previous run's copies are still in flight."}
  - {id: inv/swap-within-layer, text: "An expert is only swapped with another expert of the same layer."}
calls:
  - {name: adapt, takes: "nothing; reads the usage counts and the residency table", returns: "whether it succeeded", does: "Pairs the hottest absent experts with the coldest resident ones per layer, keeps pairs above the gain threshold, takes the best across layers up to the limit, and issues the copies."}
verification:
  - {method: none_found, checks: "No isolated test was identified. A test hook slows the copy link to make windows wait for copies.", source: "src/program/generate.cpp:13227-13231"}
observation_points: [swap_count, swap_time]
equivalence:
  - {level: bit_exact, holds_when: "the GPU and CPU expert kernels round identically", note: "Which experts are resident decides which device computes them. The project's documents say adaptive-tier timing can change rounding with some model files; see engines/strata-notes/speculation.md."}
mechanisms: [mech/hot-expert-residency]
sources:
  - {ref: "src/program/generate.cpp:13142-13314", basis: code}
  - {ref: "src/program/generate.cpp:885-923", basis: code}
```

How to read it:

- `role` comes from a fixed list, so components of different engines can be compared.
- `responsibility` is one sentence; `not_responsible_for` names what is easily mistaken for its job.
- `state.owns` are states it must keep consistent. The checker requires every state to have exactly one owner.
- `decisions` are the choices that shape its behaviour. `resolved_at` says when each is fixed: at design, at startup
  or while running. A `value` carries how it is known (`status`) and where it was read (`source`).
- `invariants` are rules it must never break.
- `equivalence` says whether it can change the output, and under which condition.
- `sources` says what the description was written from. `basis: code` means the implementation was read.
- Nothing in this file names a machine. It says `fast_memory`, never a particular memory pool.

## 3. The same component on two machines

What a component occupies on one machine is written in that machine's engine spec, under `composition`.

On the PC with a 12 GB GPU (`examples/specs/qwen-flash-on-pc.resolved.yaml`):

```yaml
- id: expert_cache
  component_ref: comp/strata/expert-cache
  manages:
  - data: expert_weights
    pool: vram
  observation_points:
  - cache_hit_count
  - cache_miss_count
  note: The slot count is decided at startup from the free memory of this pool.
- id: adaptive_tier
  component_ref: comp/strata/adaptive-tier
  uses:
  - where: cpu0
    purpose: choosing swaps on a thread beside the commit and the next draft
  observation_points:
  - swap_count
  - swap_time
```

On DGX Spark (`examples/specs/qwen-flash-on-dgx-spark.resolved.yaml`):

```yaml
- id: expert_cache
  component_ref: comp/strata/expert-cache
  manages:
  - data: expert_weights
    pool: mem0
  observation_points:
  - cache_hit_count
  - cache_miss_count
  note: Holds all 24,576 experts on this machine (46.84 GiB for IQ3_S, strata docs/DGX_SPARK_LINUX.md:76). It uses
    the model file's mapped pages in place; there is no second copy.
- id: adaptive_tier
  component_ref: comp/strata/adaptive-tier
  observation_points:
  - swap_count
  - swap_time
  active: false
  inactive_reason: Every expert is in the cache, so there is no absent expert to swap in.
```

On Spark the cache holds every expert, so the adaptive tier has nothing to swap. It is marked `active: false` with
the reason, and the policy it runs is not in that spec at all. On the PC the policy is present, with its budget
derived at startup from the memory that remains:

```yaml
- id: expert-cache
  controls:
    aspect: binding
    item: residency
    data: expert_weights
    pool: vram
  signals:
  - id: expert_heat
    per:
    - layer
    - expert
    update: raised by the number of tokens in the window that routed the expert
    decay: multiplied by the decay after every run
    note: Counted for drafted tokens as well; not rolled back when a draft is rejected.
  actions:
  - id: swap
    steps: Per layer, pair the most used absent experts with the least used resident ones; keep pairs whose usage
      ratio reaches the minimum gain; take the best pairs across all layers up to the swap limit; mark each leaving
      expert absent; wait for work already launched; copy the entering expert into the same slot; mark it resident
      when the copy lands.
  trigger: Every interval_windows verify windows; skipped while the previous run's copies are still in flight.
  scope: engine
  parameters:
    interval_windows:
      value: 4
      status: reported
      source: strata src/program/generate.cpp:887
    max_swaps:
      value: 96
      status: reported
      source: strata src/program/generate.cpp:923
    decay:
      value: 0.7
      status: reported
      source: strata src/program/generate.cpp:892
    min_gain:
      value: 1.5
      status: reported
      source: strata src/program/generate.cpp:895
    min_usage:
      value: 2
      status: reported
      source: strata src/program/generate.cpp:13158
  budget:
    derive:
      fraction: 1.0
      reserve:
        value: 700
        unit: MiB
        unit_basis: binary
        status: reported
        source: engines/strata-notes/loading.md, startup sizing
    resolved_at: startup
    source: Free fast memory minus a reserve, divided by the largest expert; read again after opening and reduced
      if the reserve was not left.
```

## 4. Deriving a new engine: the Muse design

`comp/muse/cache-policy` from `examples/systems/muse/components.yaml`. It was generated from the Strata component in
Section 2 by `tools/so_derive.py`, using the changes written in `examples/systems/muse/_derive.yaml`.

```yaml
kind: component
id: comp/muse/cache-policy
system: sys/muse-on-spark
parent: comp/muse/expert-subsystem
title: Cache policy
role: policy_runner
responsibility: Decide, for an expert that has just been read from storage, whether it enters the cache and which
  resident expert leaves, so that the cache holds the experts the current work uses most.
not_responsible_for:
- The size of the cache
- Where a missed expert is computed in the current window
runs:
- per_layer
- background
state:
  owns:
  - expert_heat
  reads:
  - residency_table
  writes:
  - residency_table
needs_resources:
- resource: cpu
  purpose: choosing what leaves
policies:
- expert-cache
decisions:
- id: admit-rule
  text: 'The condition under which a missed expert enters the cache: always, or only when its usage count exceeds
    that of the least used resident expert of the layer.'
  resolved_at: design
- id: decay
  text: How fast usage counts fade.
  resolved_at: design
- id: per-layer-share
  text: Whether every layer has the same number of slots or slots move to the layers with the most misses.
  resolved_at: runtime
- id: starting-contents
  text: 'What the cache holds before any request: nothing, or the experts a recorded usage profile ranks highest.'
  resolved_at: startup
invariants:
- id: inv/read-ready
  text: An entering expert is marked resident only after its bytes have fully arrived.
- id: inv/no-overwrite-while-read
  text: A slot is not overwritten while a computation that may read it is in progress.
verification:
- method: invariant_test
  checks: A slot is never overwritten while a computation reads it, under injected slow reads.
  invariants:
  - inv/no-overwrite-while-read
- method: measurement
  checks: Hit rate on a recorded routing trace, replayed without running the model.
observation_points:
- swap_count
- swap_time
equivalence: bit_exact
mechanisms:
- mech/hot-expert-residency
derived_from:
- component: comp/strata/adaptive-tier
  carried_as: adapted
  adaptation: Strata swaps a bounded number of experts every few windows from memory to memory. Here every miss
    already brings the expert in from storage, so the question is which resident expert it replaces, if any. The
    usage counts and their decay are kept.
- component: comp/ds4/expert-eviction
  carried_as: adapted
  adaptation: Strata swaps a bounded number of experts every few windows from memory to memory. Here every miss
    already brings the expert in from storage, so the question is which resident expert it replaces, if any. The
    usage counts and their decay are kept.
sources:
- ref: comp/strata/adaptive-tier
  basis: proposal
- ref: comp/ds4/expert-eviction
  basis: proposal
```

How to read it:

- `derived_from` names the existing components it was taken from. `carried_as` is `reused` or `adapted`; an adapted
  component must say what changed and which property of the model or hardware forces it.
- The decisions have no values. The numbers tuned for Strata's model were removed, so each is an open choice again.
- `sources` has `basis: proposal`: there is no implementation.
- `verification` says how this component will be checked on its own.

Components of the source engine that were not carried over are listed in the new system with a reason. The checker
refuses a derivation in which any leaf component of the main source engine is unaccounted for.

```yaml
- component: comp/strata/native-weight-loader
  why: does_not_apply
  note: It serves tensors Strata keeps in GGUF form. Muse's prepared files have one form and one loader.
- component: comp/strata/host-memory-admission
  why: does_not_apply
  note: It admits a page-locked host copy of every expert and of the lookup table. Muse's experts are three times
    the machine's memory and the model has no lookup table.
- component: comp/strata/slot-scheduler
  why: postponed
  note: A second conversation needs its own attention state in memory, taken from the expert cache.
```

## 5. A requirement

From `examples/specs/muse-spark-open-on-dgx-spark.target.yaml`.

```yaml
- id: c-mem
  quantity: memory_budget
  kind: pass_fail
  status: proposed
  value: 80
  unit: GB
  unit_basis: decimal
  pool: mem0
  accounting_boundary: 'Everything the engine''s container holds in the unified pool at any moment: allocations
    of the process on CPU and GPU, and page cache attributable to the files it reads. The operating system and other
    processes are outside.'
  source: 'scope-slide#memory: Strata-Spark: 80 GB Unified Memory'
  note: The scope page names three figures. 128 GB is the machine's nominal memory, of which 121.6 GB is reported
    allocatable, so it cannot be a budget. 12 GB is called a GPU working-set figure, and this machine has no separate
    GPU memory to apply it to. 80 GB is the one figure that is a budget for this machine. The choice, the unit basis
    and the accounting boundary are proposals to be confirmed.
- id: c-context
  quantity: context_length
  kind: pass_fail
  value: UNSET
  unit: tokens
  note: The model allows 1,000,000 tokens. The attention state for the offered context is taken from the same 80
    GB as the expert cache, so the engine cannot be sized until this is given. The scope page does not give it.
```

How to read it:

- A requirement on a registered quantity must carry that quantity's defining fields. For a memory budget: the unit
  basis (decimal or binary), the pool, and what is counted.
- `status: proposed` marks a value we put forward for confirmation. `UNSET` marks something only the project can
  decide; the checker reports each as a gap and says who should answer.

## Checking these files yourself

From the `system-ontology/` directory:

```bash
python tools/so_check.py validate
```

```bash
python tools/so_check.py system sys/strata
```

```bash
python tools/so_check.py system sys/muse-on-spark
```

```bash
python tools/so_check.py check spec/muse-spark-open-on-dgx-spark/target
```

Messages are in English; the bracketed labels are terms of the dictionary.
