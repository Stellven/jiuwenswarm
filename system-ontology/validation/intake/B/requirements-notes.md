# Requirements CC notes: research_brief.json

## 1. Carried from the context sources, and where

- **target.yaml** (the main source, through the accepted Intent):
  - `given.model` and `given.hardware`: `constraints` con-model and con-hardware (categorical `eq`).
  - `boundary.packaging: container`: con-packaging, req-container.
  - `interface.input` and `interface.output` (text): con-input-text, con-output-text, req-text-io.
  - `execution/state/composition/policy/binding: open`: `in_scope` scope-factory-open.
  - `contract.c-mem` (80 GB decimal, mem0, accounting boundary, proposed): con-memory-budget (`le 80 GB`, with the decimal basis, boundary and proposed status in the text), req-memory-budget.
  - `c-context` (pass/fail, value UNSET): con-context-length (`qualitative`, null value), req-context-length, unresolved item.
  - `c-quality` (baseline, comparison, task set and threshold UNSET): req-quality, `target_metrics` tm-quality (null comparison).
  - `c-ttft`, `c-decode`, `c-peak` (report, proposed definitions): req-report-*, tm-ttft, tm-decode, tm-peak-memory (null comparison, null unit).
  - `contract.workload` and `allowed_transformations`, `delivery.model_checkpoint` (all UNSET), `given.environment`, `boundary.form`, `interface.streaming` (UNSET): constraints con-fixed-workload and con-one-checkpoint, plus `unresolved_items`.
  - `delivery.deliverables` (four, required): `deliverables` (artifact_type uses the target's item names), `in_scope`, req-container, req-clean-rebuild, req-benchmark-report, req-run-artifacts.
- **model.yaml**: model identity (con-model); vendor 700 GB / 2000 GB memory statements, multimodal input, derived sizes, missing attention-state size, config.json needing a login, the Muse Model License: unresolved items only (unr-vendor-memory, unr-non-text-modalities, unr-model-facts-unverified, unr-model-resources-not-supplied).
- **machine.yaml**: machine identity (con-hardware); mem0 as the budget pool (in constraint text); missing SSD read bandwidth (unr-model-facts-unverified).
- **node-types.yaml**: bound as `input_bindings` in-node-types (reference_document) only; its role is an unresolved, non-blocking item. No requirement drawn from it.
- All four sources are in `context_refs`, `resource_refs` and `input_bindings`. `ext.req.intent_links` maps every Brief item back to the Intent IR ids it preserves.

## 2. Found in the sources with no field

- The given facts of the model and machine (816B/42B parameters, 62 layers, 8 of 256 experts, 1,000,000-token vendor context, vocab, BF16/NVFP4, safetensors; 20-core arm64 CPU, Blackwell GPU, 273 GB/s, NVMe up to 4 TB with page-in path). The Brief has no field for given facts; they stay reachable only through `input_bindings` refs (and a few in constraint/unresolved text).
- Statement status (`vendor_stated`, `derived`, `proposed`, `UNSET`, `open`): no status field; written into the text.
- Unit basis (decimal GB) and the memory accounting boundary: no fields; in the constraint text.
- The target's notes (why 80 GB was chosen, 121.6 GB allocatable, 12 GB GPU working-set figure): only summarised in unr-memory-figure.
- machine.yaml's unstated GB basis for the 128 GB nominal, and the separate 64 GB configuration: not carried (no requirement is affected).
- node-types content (effect levels and their relation to `allowed_transformations`): not carried; no requirement in it.
- Source spans: the Brief's `source_refs` are whole-document `Ref`s, so the Intent's span precision is lost; ids in `ext.req.intent_links` keep the path back to the spans.

## 3. Blocking unresolved items and why

Rule applied: an item is blocking when a mandatory pass/fail requirement (or the sizing it rests on) cannot be stated or judged without it, the target reserves it to the project (UNSET, not `open`), and no protected default authorises filling it (none was supplied). Items that touch only report-only quantities or factory-open choices, facts to be read or measured, or ambiguities the request itself settles ("take them as the statement of what is wanted") are non-blocking.

- **unr-context-length**: pass/fail requirement with no value; the target says the engine cannot be sized without it.
- **unr-allowed-transformations**: decides which quality comparison (identical tokens or task-score threshold) the pass/fail quality requirement uses.
- **unr-quality-taskset-threshold**: needed to judge quality if transformations are allowed; blocking while that is open, moot if they are not.
- **unr-workload**: the fixed workload is required and UNSET; the memory-budget pass/fail and all reported measurements depend on it, and the target reserves it to the project, so the factory may not pick one.
- **unr-checkpoint**: the single checkpoint is UNSET; the engine's primary input and the quality baseline's meaning depend on it. NVFP4 is implied by the proposed baseline but not set, and choosing it would be an unauthorised default.

Non-blocking: proposed status of the budget, baseline and timing definitions; the 80 GB figure choice; the vendor 700 GB vs 80 GB tension; form, environment, streaming; non-text modalities; unverified model and machine facts; model resources not supplied; node-types role. With five blocking items the Brief cannot be accepted; the gate should halt and show the five clarifications.

## 4. Schema fit for an engine-building request

- `domain_lane` is fixed to `scientific_research`; this is an engineering build. Kept the constant.
- `input_bindings.role` has no role for a requirements specification or a hardware/model description; all four sources are bound as `reference_document`.
- `target_metrics` has no notion of "report only, no threshold" vs "pass/fail with unknown threshold": both use `comparison: null`, and the distinction is in `target_text` and the requirement text. The memory budget is a constraint (as in the Intent), not a metric.
- A pass/fail requirement with an unknown value (context length) cannot use `ge` without a number, so it is `qualitative` with null value, plus a blocking unresolved item.
- The quality comparison is conditional on another unset field; there is no conditional field, so the condition is in text and in the item dependency.
- Constraint `scope` (compiler / research_run / scientific_execution) was mapped as: runtime engine properties -> `scientific_execution`; packaging and measurement workload -> `research_run`.
- No status, unit-basis or accounting-boundary fields; carried in text.
- `unresolved_items.affected_fields` uses JSON pointers into the Brief (checked to resolve); the Intent IR used field names.
