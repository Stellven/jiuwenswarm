---
id: contracts.index.services
type: index
level: detail
status: draft
provides: []
depends_on: []
---

# Index: service and bridge contracts

Schema file: [services-v1.schema.json](services-v1.schema.json). Fixtures: [fixtures/services-v1.json](fixtures/services-v1.json), a valid and an invalid case for every def. Helpers (ref, id, hash, nullable_ref, [ext](../schemas/common.md#term-ext), reason) are shared building [blocks](../system/modules.md#term-block) used by every other schema.

| Schema def | Family | Message | Sender -> receiver | Transport | Described in |
|---|---|---|---|---|---|
| `services-v1.schema.json#retry_profile` | Profile | [RetryProfile](../schemas/profiles.md#term-retryprofile) for each [effect class](../capsule/fields.md#term-effect-class) (zero retries in M1) | supervisor -> runner | in process | [system/lifecycle.md](../system/lifecycle.md) |
| `services-v1.schema.json#ref` | Helper | Reference to a stored record or artifact | any | shared helper | helper |
| `services-v1.schema.json#id` | Helper | Identifier | any | shared helper | helper |
| `services-v1.schema.json#hash` | Helper | SHA-256 string | any | shared helper | helper |
| `services-v1.schema.json#nullable_ref` | Helper | Optional reference | any | shared helper | helper |
| `services-v1.schema.json#ext` | Helper | Extension map | any | shared helper | helper |
| `services-v1.schema.json#reason` | Helper | Reason code plus detail | any | shared helper | helper |
| `services-v1.schema.json#error` | Helper | Public error envelope | service -> client | HTTP or UDS | [README](README.md) |
| `services-v1.schema.json#planner_request` | Call | Ask the planner for a DAG | supervisor -> planner | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#selection` | Helper | One capability chosen for a node | planner -> [validator](../system/planner.md#term-plan-validator) | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#objective_binding` | Helper | Which node covers which requirement | planner -> validator | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#planner_proposal` | Record | The proposed DAG envelope | planner -> validator | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#validation_request` | Call | Ask the validator to check a proposal | supervisor -> validator | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#finding` | Helper | One validation problem | validator -> supervisor | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#plan_finding_code` | Helper | Closed set of plan validation finding codes (CYCLE, MISSING_PRODUCER, WRONG_VERSION, UNREACHABLE_OBJECTIVE, DENIED_EFFECT, MISSING_GATE, BUDGET_EXCEEDED, TYPE_MISMATCH, UNKNOWN_CAPABILITY, MISSING_INPUT) | validator -> supervisor | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#plan_validation` | Call | Validator verdict and normalized plan | validator -> supervisor | in process | [system/planner.md](../system/planner.md) |
| `services-v1.schema.json#experiment_request` | Call | Start an isolated experiment run | experiment client -> supervisor | HTTP | [system/experiments.md](../system/experiments.md) |
| `services-v1.schema.json#experiment_profile` | Profile | Allowed features of an experiment | experiment entry | config | [system/experiments.md](../system/experiments.md) |
| `services-v1.schema.json#benchmark_request` | Call | Run one task headless | benchmark client -> supervisor | HTTP | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#run_handle` | Report | Handle for a started run | supervisor -> client | HTTP | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#export_request` | Call | Ask for a sealed export | client -> supervisor | HTTP | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#measurement` | Helper | One measured value with unit and evidence | measurement service -> export | in process | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#step` | Helper | One step record in an export | export | file | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#model_call` | Helper | One model call record in an export | export | file | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#artifact` | Helper | One artifact record in an export | export | file | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#deviation` | Helper | A recorded departure from the production profile | export | file | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#benchmark_export` | Report | The sealed run export | supervisor -> client | HTTP | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#seed` | Helper | Requested and effective seed | export | file | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#benchmark_profiles` | Profile | Profiles a run used | export | file | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#readiness` | Report | Ready or not-ready answer | service -> client | HTTP | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#export_handle` | Report | Handle to a sealed export | supervisor -> client | HTTP | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#abort_request` | Call | Abort a run | client -> supervisor | HTTP | [system/benchmark-export.md](../system/benchmark-export.md) |
| `services-v1.schema.json#routing_request` | Call | Ask the router for an endpoint for one call | runner -> router | in process | [model-routing/README.md](../model-routing/README.md) |
| `services-v1.schema.json#routing_decision` | Record | The router answer | router -> [bridge](../system/model-bridge.md#term-model-bridge) | in process | [model-routing/README.md](../model-routing/README.md) |
| `services-v1.schema.json#ablation_action` | Helper | Disable or replace one component in a study | experiment entry | config | [system/experiments.md](../system/experiments.md) |
| `services-v1.schema.json#ablation_study` | Profile | A preregistered ablation study | experiment entry | config | [system/experiments.md](../system/experiments.md) |
| `services-v1.schema.json#experimental_advance` | Record | Experiment-only release evidence | supervisor | store | [system/experiments.md](../system/experiments.md) |
| `services-v1.schema.json#auth_request` | Call | Manage the Codex login | installer -> auth provider | local UDS | [system/model-auth.md](../system/model-auth.md) |
| `services-v1.schema.json#auth_result` | Call | Login status answer | auth provider -> installer | local UDS | [system/model-auth.md](../system/model-auth.md) |
| `services-v1.schema.json#experimental_gate_evidence` | Record | Experiment-only [Gate](../verification.md#term-gate) evidence | supervisor | store | [system/experiments.md](../system/experiments.md) |
| `services-v1.schema.json#model_call_scope` | Helper | Who a model call belongs to | supervisor -> bridge | UDS | [system/model-bridge.md](../system/model-bridge.md) |
| `services-v1.schema.json#scoped_capture_ref` | Helper | Reference to captured model bytes | bridge -> supervisor | UDS | [system/model-bridge.md](../system/model-bridge.md) |
| `services-v1.schema.json#private_model_capture` | Record | Capture kept by the oracle or [RSI](../rsi.md#term-rsi) controller | bridge | store | [system/model-bridge.md](../system/model-bridge.md) |
| `services-v1.schema.json#model_bridge_request` | Call | One model [turn](../system/model-bridge.md#term-model-turn) request | runner or planner -> bridge | UDS | [system/model-bridge.md](../system/model-bridge.md) |
| `services-v1.schema.json#model_bridge_result` | Call | The model turn result | bridge -> runner or planner | UDS | [system/model-bridge.md](../system/model-bridge.md) |
| `services-v1.schema.json#model_call_limits` | Helper | Time and turn limits for one call | supervisor -> bridge | UDS | [system/model-bridge.md](../system/model-bridge.md) |
| `services-v1.schema.json#planning_reservation` | Helper | Reservation made before a planner call | supervisor | store | [system/records.md](../system/records.md) |
| `services-v1.schema.json#model_call_reservation` | Helper | Reservation made before a model call | supervisor | store | [system/records.md](../system/records.md) |
