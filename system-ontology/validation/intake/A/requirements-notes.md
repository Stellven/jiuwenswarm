# Notes on research_brief.json (Requirements CC, req-A)

## 1. What from the context sources went into the Brief, and where

- **target.yaml** (the main source, which the request adopts as the statement of what is wanted):
  - `given.model` and `given.hardware` went to `constraints` con-model and con-hardware (categorical `eq`) and to req-engine.
  - `boundary.packaging: container` went to con-packaging (`eq "container"`) and req-deliver-container.
  - `interface.input/output: text` went to con-input-text, con-output-text and req-text-interface.
  - `execution/state/composition/policy/binding: open` went to `in_scope` is-factory-open.
  - `c-mem` went to con-memory-budget (`le`, 80, `GB`, decimal and the accounting boundary in the text) and req-memory-budget. Its "proposed" status went to ur-memory-budget.
  - `c-context`, `c-quality`, `c-ttft`, `c-decode` and `c-peak` went to `target_metrics` (all with `comparison: null` and no invented value) and to mandatory requirements. Their timing and accounting boundaries went to `out_of_scope` (oos-os-memory, oos-model-load, oos-first-token-decode).
  - The four `delivery.deliverables` went to `deliverables`, `in_scope` and mandatory requirements.
  - Every UNSET field (environment, form, streaming, context value, task set, threshold, allowed transformations, workload, checkpoint) and the missing scope page went to `unresolved_items`.
- **model.yaml**: the 700 GB / 2000 GB "VRAM required" figures went to ur-vram-vs-budget. The derived weight sizes, the unread config.json and the untied-head question went to ur-model-sizes. The multimodal input and perception encoder went to ur-modality. The BF16/NVFP4 offer went to ur-checkpoint.
- **machine.yaml**: the 128 GB configuration went to con-hardware. The 64 GB configuration exclusion went to oos-64gb. The SSD bandwidth that is not given went to ur-ssd-bandwidth. The GB unit basis that is not stated went to ur-scope-page.
- All three files are in `context_refs`, `resource_refs` and `input_bindings` (role `reference_document`).

## 2. What from the context sources had no field

- Model structure: 816B total / 42B active parameters, 62 layers, hidden size 8192, vocabulary 202,048, 1,000,000-token context, 8-of-256 expert routing, 15,872 experts, the derived expert and shared weight sizes, the attention-state estimate, safetensors and the licence.
- Machine facts: 20 arm64 cores, Blackwell GB10 GPU, 273 GB/s bandwidth, the unified pool with no separate GPU memory, the NVMe page-in path, and 121.6 GB allocatable.
- The Brief has no field for facts about given entities. They are neither requirements, constraints nor targets. They stay reachable through `context_refs` and `input_bindings` and were not copied. Only those that create an open question are named in `unresolved_items`.
- The target's statuses (stated, `proposed`, UNSET, `open`) also have no field. They are expressed in statement text and in unresolved items.
- The Intent `context` entities and the uncertainty source spans have no counterpart either. A trace from every Intent ID to Brief JSON pointers is kept in `ext["requirements-cc.intent_trace"]`, which is diagnostic only.

## 3. Blocking unresolved items, and why

The rule applied comes from the factory pages: block material uncertainty instead of manufacturing requirements. No defaults are authorized. An item is blocking when it meets two conditions. First, the target reserves the value for the project (UNSET). Second, without the value a mandatory pass/fail requirement cannot be judged, or the engine's model input cannot be fixed. Proceeding would then require the factory to invent the requirement.

- **ur-context-length** (blocking): this is a pass/fail requirement with no value. The target says the engine cannot be sized until the value is given.
- **ur-quality-taskset-threshold** (blocking): this is a pass/fail requirement. On its task-score branch it has no task set and no threshold.
- **ur-allowed-transformations** (blocking): it decides which branch of the pass/fail quality rule applies, and what the engine may change in the computation.
- **ur-checkpoint** (blocking): the checkpoint is the engine's model input, which the target reserves for the project (UNSET). No checkpoint was supplied. NVFP4 is strongly suggested but not chosen.

The other ten items are non-blocking:
- The memory budget and the report definitions are concrete proposals that the request adopts.
- The workload only affects report-only quantities.
- Form, streaming and environment are unset, but no pass/fail requirement depends on them.
- The rest are model or machine facts, or the missing scope page.

Note that the Intent IR marked every uncertainty non-blocking and declared readiness `ready`. Four blocking items mean this Brief halts at the Requirements gate until the project answers them.

## 4. Schema fit for an inference-engine request

- `domain_lane` is fixed to `scientific_research`. This is an engineering build, but the constant was kept because the schema allows nothing else.
- Constraint `scope` offers compiler, research_run and scientific_execution. Runtime limits on the engine (model, hardware, interface, memory) were put under `scientific_execution`. Packaging and the statement-of-want were put under `research_run`.
- `target_metrics.comparison` only expresses numeric thresholds. The quality rule ("same output tokens as the baseline, else task score not below a threshold") and report-only quantities have no shape, so `comparison` is null and the rule is kept in `target_text`. Pass/fail versus report-only is stated in text.
- The target's "proposed" status has no field. The values are carried with `origin: user`, because the request adopts the files as the statement of what is wanted. Their status is flagged in text and in non-blocking unresolved items.
- `input_bindings.role` has no fit for a model checkpoint or a hardware description. All three ontology files are bound as `reference_document`. No checkpoint resource exists to bind.
- `unit` for ttft, decode rate and peak memory is null, because the target gives none.
- `Uncertainty.affected_fields` was written as JSON pointers into the Brief.
