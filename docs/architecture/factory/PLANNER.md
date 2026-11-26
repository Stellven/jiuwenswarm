# The AI planner: one TaskInput in, a proven TaskGraph out

The planner is a self-contained compiler and formal prover: it takes a single
`TaskInput` (`factory.task-input/1`, with no multi-arm experiment contract required) plus
the full Capability Capsules catalog (`plan_catalog.prompt_view`), and produces a
statically checked (M1 bridged + M2 rules) and TLC-proven `TaskGraph` (`graph.json`
plus `contract.json`, `plan.json`, `task.json`, `verification.json`, `derivation.json`).

## How a graph is made

1. **Host selection & full CC view (`plan_select` + `plan_catalog`).** From `TaskInput`
   and the capsule catalog (`plan_catalog`), the host deterministically computes:
   - hard filters: realizable capsule (`builder` or `verify_pack` `tool` CC, not excluded),
     H2 (`base.commit == subject.engine.revision`), H3 (`changes <= allowed_effects`),
     H4 (`hints.must_include`);
   - soft features: F1 hardware compatibility (`supported.host` vs `TaskInput.target`),
     F2 semantic match (`objective` + `acceptance_criteria` + `subject.model`), F3
     acceptance type, F4 ontology `slices`, `regions`, and `touches`;
   - pairwise interference matrix (`touches` + `modifies_region`) and merge topologies
     (`M1`, `M2`, `M3`), alongside the full CC Library declaration view (`prompt_view`).
2. **Model decisions (`plan_ir`: `factory.plan-ir/1`).** One fresh, tool-free governed
   turn (`invoke_governed`) selects capsules and designs the TaskGraph directly:
   - `selected_capsules`: 1 or more `{capsule, why}` from `selection.candidates` (or
     `unrealizable: {why}` when nothing fits);
   - optional `units` grouping (2 builder capsules may share a unit only within the same
     ontology `slice`);
   - `preflight` decisions (`add: true/false`) for every selected unit with an F1 risk;
   - `merge` option (`M1`/`M2`/`M3`) iff 2 or more code-diff units are selected;
   - `steps`: autonomous list of TaskGraph steps (`id`, `kind`, `objective`, `depends_on`,
     `capsules`, optional `limits`/`criteria`/`outputs`/`workspace`) ending at one terminal
     `deliver` leaf and binding all `selected_capsules` plus any helper/analysis CCs;
   - optional `priority` ordering, extra `criteria`, and tightened `limits`.
3. **Host compilation (`plan_compile`).** Deterministically compiles the declared `steps`
   (honoring `priority` and expanding M2/M3 merges when applicable), binding
   `TaskInput.acceptance_criteria` into step `requirement_ids` and `criteria`, typed
   ports, verifiers, minimal `authority_ceiling`, and logging every rule to `derivation.json`.
4. **Static checks (`plan_checks` + `m1_verifier_bridge`).** Runs `node_contract.problems`,
   `planner.check_plan`, bridged M1 `binding.plan_checks`, and M2 semantic checks
   (`coverage`, `hints`, `catalog_closure`, `authority`, `join_before_build`, `port_types`,
   `purpose`, `budget`).
5. **Internal TLC proof (`tla_check` + `tla_graph`).** Renders `tla/TaskGraphExec.tla` /
   self-contained `Graph.tla` internally and exhaustively verifies static `ASSUME` invariants
   plus two runs: `safety` (`Cooperative = FALSE`) and `delivery` (`Cooperative = TRUE`).
6. **Feedback & acceptance.** Problems go back to the model for at most 3 rounds. Accepted
   runs pass the `init` gate (`planner.plan_for_task`), emitting standard JSON deliverables
   with verified `graph.json` (including `execution_model` and `verification`) as the sole
   downloadable external output, while downstream `scheduler`, `node_check`, `controller`,
   and `planner` remain completely untouched.

## TaskInput (`factory.task-input/1`)

Defined in `schemas/requirements-1.schema.json`:

- `requirements_id` / `task_id`, `objective`;
- `subject`: pinned `engine` (`name`, `revision`) and exact `model` (`name`, `format`, `manifest`);
- `target`: single-node hardware (`profile`, `machine`, `arch`, `cuda`, `sm`, `memory_gb`, `node_count: 1`);
- `acceptance_criteria`: structured `correctness`, `metric`, and `constraint` items;
- `constraints`: `allowed_effects` and `budget` (`max_turns`, `wall_clock_s`);
- optional `hints` (`must_include`, `excludes`, `preferred_merge`), `notes`, `task_template`,
  and optional `contract_id` (legacy compatibility).

## Current Target Baseline Alignment

- **Subject engine & model baseline**: customized `llama.cpp` inference engine built specifically
  for `Muse-Spark-Open-816B-A42B-NVFP4` (`unsloth/Muse-Spark-Open-816B-A42B-NVFP4`, format
  `safetensors-nvfp4`), as captured in `requirements/muse-q2-ttft-v2.json`.
- **Target hardware**: single-node **DGX Spark GB10** (`arch: arm64`, `CUDA 13`, `sm_121`, `128 GB`
  unified memory, `node_count: 1`).

## Where to use it

- **Verified JSON Deliverables (`graph.json`)**: Planner emits verified `graph.json`
  (embedding `factory.taskgraph/1`, `execution_model`, `static_checks`, and TLC `proven`
  runs) as the sole downloadable external output, alongside `task.json` / `contract.json` /
  `plan.json` for standard downstream `jiuwenswarm-factory init`. TLA+ (`tla_graph` /
  `tla_check`) stays strictly internal to the Planner verification gate.
- **CLI**: `jiuwenswarm-factory synthesize <task_input.json>` (`--replay <run>`),
  `jiuwenswarm-factory init <task.json>`, and
  `jiuwenswarm-factory verify-plan <contract.json> --requirements <task_input.json>`.
- **Web**: Factory runs → Planner (`#planner`), served under `/api/factory/planner`
  (including `GET /api/factory/planner/runs/{id}/graph.json` and `/api/factory/planner/ablation`).
