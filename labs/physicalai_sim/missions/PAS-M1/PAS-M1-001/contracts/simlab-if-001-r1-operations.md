# SIMLAB-IF-001@r1 operations and typed errors (phase 1)
Implements [SIMLAB-IF-001@r1](../TASK.md#simlab-if-001-at-r1). The record schemas (`simlab-experiment`, `simlab-result`, `simlab-manifest`, `simlab-error`) are exported as JSON Schema from the implementation's models into `labs/physicalai_sim/src/simlab/schemas/`, each labeled `simlab-if-001@r1`; a drift check keeps this contract, the models and the export equal. The MCP tools, Python client methods and CLI subcommands use the operation names below with identical inputs, outputs and errors.

## Operations
| Operation | Input | Output | Side effect | Errors |
| --- | --- | --- | --- | --- |
| `capability` | none | Registry entries (`capability`, `status` ∈ `admitted`/`supported`/`excluded`/`missing`, `reason`, `evidence_ref`) | None | — |
| `validate` | Experiment | `{findings: simlab-error[]}` (empty when valid) | None | `E_SCHEMA_*`, `E_SEMANTIC_*` as findings |
| `submit` | Experiment (bound) | `{run_id, experiment_id}` or `{findings}` | Creates experiment (if new) and a run | Findings; `E_NOT_BOUND` |
| `status` | `run_id` | Run status, attempt counts per status | None | `E_UNKNOWN_RUN` |
| `result` | `run_id` | `simlab-result` | None | `E_UNKNOWN_RUN` |
| `query` | `run_id` plus any of `arm_id`, `trial_id`, `t_start`, `t_end`, `signal` | Matching trace and measurement descriptors | None | `E_UNKNOWN_RUN`, `E_UNKNOWN_SIGNAL` |
| `fetch` | Descriptor from `query`, optional time range | Data (inline up to a size cap, else a blob reference) | None | `E_UNKNOWN_REF` |
| `replay` | `run_id` | New `run_id` with `run_kind = replay` | Creates a run | `E_UNKNOWN_RUN`, `E_NOT_REPLAYABLE` (different image digest) |
| `cancel` | `run_id` | Final status | Run `CANCELLED`, running attempt `INTERRUPTED` | `E_UNKNOWN_RUN`, `E_ALREADY_TERMINAL` |
| `wait` (TASK §5 A3) | `run_id`, optional `timeout_s` | Run status when it ends or the timeout passes | None | `E_UNKNOWN_RUN` |
| `branch` | `checkpoint_id` plus authoring changes | Draft or experiment with `parent = {checkpoint_id}` | Creates a draft | `E_UNKNOWN_CHECKPOINT` |
| Authoring: `draft_create`, `geometry_put`, `collision_put`, `model_file_put`, `procedure_put`, `intervention_put`, `measurement_put`, `observation_put`, `component_put`, `artifact_list`, `artifact_get` and `artifact_delete` (TASK §5 A3), `bind` | Draft ID plus artifact content | Artifact SHA-256; `bind` returns `simlab-manifest` | Writes the draft workspace; `bind` writes immutable blobs | `E_UNKNOWN_DRAFT`, `E_BOUND`, `E_EXTENSION_POINT`, schema findings |

Phase 2 to 4 operations (`preview`, `pilot`, `release_inspection`, `fresh_replication`, `pause`, `resume`, `stream`) are reserved names; their contracts are written by their provider TASKs against IF-001@r1.

## Typed error object
`{code: string, message: string, path: string (JSON pointer into the input, or "" ), severity: "error" | "warning"}`. Codes are stable within r1. Initial catalogue (extended additively, with each extension recorded in TASK §5):

| Code | Meaning |
| --- | --- |
| `E_SCHEMA_REQUIRED` / `E_SCHEMA_TYPE` / `E_SCHEMA_ENUM` / `E_SCHEMA_UNKNOWN_FIELD` | Record does not match the IF-001@r1 schema |
| `E_SEMANTIC_NO_ORIGIN` | A protocol item lacks an origin |
| `E_SEMANTIC_PARENT_MISSING` | Parent run or checkpoint does not exist |
| `E_SEMANTIC_COMPARISON_INCOMPLETE` | A comparison lacks unit of inference, pairing, aggregation or required precision |
| `E_SEMANTIC_ZERO_TRIALS` | The design yields no trial |
| `E_SEMANTIC_UNDECLARED_CHECKPOINT` | Save requested at an undeclared point |
| `E_SEMANTIC_MJCF_COMPILE` | Model file does not compile (engine message included) |
| `E_SEMANTIC_ASSET_HASH` | An asset is missing from the manifest or its hash differs |
| `E_SEMANTIC_ENGINE_FLAG` | A setting that breaks exact replay (for example `ipc`) is enabled |
| `E_IMMUTABLE` | Attempt to modify a submitted experiment or bound manifest |
| `E_NOT_BOUND`, `E_BOUND`, `E_UNKNOWN_*`, `E_ALREADY_TERMINAL`, `E_NOT_REPLAYABLE`, `E_EXTENSION_POINT` | Operation errors as named |

Additions recorded in TASK §5 A3: `E_SEMANTIC_DUPLICATE_ID`, `E_SEMANTIC_UNKNOWN_REF`, `E_SEMANTIC_UNKNOWN_SIGNAL`, `E_SEMANTIC_UNKNOWN_TARGET`, `E_SEMANTIC_TEMPLATE`, `E_SEMANTIC_CONFIG`, `E_SEMANTIC_ENGINE`, `E_SEMANTIC_MANIFEST_BINDING`, `E_SEMANTIC_LIMITS`, `E_SEMANTIC_CHECKPOINT_INCOMPATIBLE`, `E_UNKNOWN_OPERATION`, `E_INVALID_INPUT`, `E_RESERVED_OPERATION`, `E_DATA_DIR`, `E_INTERNAL`. The authoritative catalogue is `labs/physicalai_sim/src/simlab/contracts/errors.py`; reserved operations return `E_RESERVED_OPERATION` until their provider TASK implements them.
