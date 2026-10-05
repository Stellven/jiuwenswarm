---
id: contracts.index.execution
type: index
level: detail
status: draft
provides: []
depends_on: []
---

# Execution and control contracts index

Wire shapes for the run lifecycle, freeze, dispatch, system records and events. Schema file: [execution-v1.schema.json](execution-v1.schema.json). Fixtures: [fixtures/execution-v1.json](fixtures/execution-v1.json). The `exit_code` def (0 success, 2 rejected, 3 [halted](../system/lifecycle.md#term-halt), 4 environment unavailable) is an internal helper shared by run_status_view, cli_json_output and [halt_report](../system/lifecycle.md#term-halt-report) and launch_result. Shared definitions (ref, id, hash, reason, error, run_handle, step, reservations) come from [services-v1.schema.json](services-v1.schema.json). Behavior stays on the linked pages.

| Schema def | Family | Message | Sender -> receiver | Transport | Described in |
|---|---|---|---|---|---|
| `execution-v1.schema.json#system_ref` | Helper | Reference to a [system record](../system/records.md#term-systemrecord) | store (M12) -> any consumer | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#trial_file` | Helper | One file of a private [RSI](../rsi.md#term-rsi) trial (path, hash, content ref) | controller -> oracle | private evidence root | [records](../system/records.md) |
| `execution-v1.schema.json#skill_issue` | Helper | One input problem a skill reports (INPUT_AMBIGUOUS, INPUT_INCOMPLETE, INPUT_CONTRADICTORY) | model -> skill handler | model reply text (JSON) | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#launch_request` | Call | Start a run (prompt, channel, workspace, optional seed and headless) | CLI, Web, benchmark client -> supervisor | loopback HTTP JSON (authenticated) or in-process Python call | [workstation](../system/workstation.md), [lifecycle](../system/lifecycle.md) |
| `execution-v1.schema.json#launch_result` | Call | Run handle or typed rejection | supervisor -> CLI, Web, benchmark client | loopback HTTP JSON (authenticated) | [workstation](../system/workstation.md), [lifecycle](../system/lifecycle.md) |
| `execution-v1.schema.json#resume_request` | Call | Continue a halted run after recorded human review | terminal -> supervisor | in-process Python call | [lifecycle](../system/lifecycle.md) |
| `execution-v1.schema.json#abort_request_run` | Call | Stop a run, evidence kept | CLI, Web -> supervisor | loopback HTTP JSON (authenticated) | [lifecycle](../system/lifecycle.md), [workstation](../system/workstation.md) |
| `execution-v1.schema.json#run_status_view` | Report | RunView: state, phase, current step, [gate verdict](../capsule/gate-host.md#term-gate-verdict), outputs | supervisor -> CLI, Web, TUI | loopback HTTP JSON (authenticated) | [workstation](../system/workstation.md) |
| `execution-v1.schema.json#cli_json_output` | Report | JSON printed by cc status, inspect, doctor | CLI -> user or script | stdout | [workstation](../system/workstation.md) |
| `execution-v1.schema.json#run_manifest` | Record | Rebuildable run manifest with both plan refs and step [phases](../system/lifecycle.md#term-phase) | supervisor -> readers, exporters | in-process Python call | [records](../system/records.md) |
| `execution-v1.schema.json#local_session_token` | Record | Ephemeral local session token file | launcher -> in-container CLI | file, mode 0600 | [workstation](../system/workstation.md) |
| `execution-v1.schema.json#record_input_request` | Call | Record a control or human input value as an Artifact | launcher, gate host -> runner | in-process Python call | [runner](../capsule/runner-handlers.md#values-how-each-port-type-travels) |
| `execution-v1.schema.json#commit_request` | Call | Runner asks the supervisor to commit an [Observation](../schemas/observation.md#term-observation), Artifact or capture on its behalf | runner -> supervisor | authenticated local socket, length-prefixed frames | [runner](../capsule/runner.md), [storage](../system/storage.md) |
| `execution-v1.schema.json#commit_result` | Call | Committed ref, or a refusal or conflict with a reason | supervisor -> runner | authenticated local socket, length-prefixed frames | [runner](../capsule/runner.md), [storage](../system/storage.md) |
| `execution-v1.schema.json#freeze_request` | Call | Freeze one phase (validated plan to [Bindings](../schemas/binding.md#term-binding)) | launcher, supervisor -> freeze (M03) | in-process Python call | [toolchain](../capsule/toolchain.md) |
| `execution-v1.schema.json#commit_batch_manifest` | Record | Manifest of one atomic commit [batch](../system/storage.md#term-commit-batch) (all Bindings of a phase) | store (M12) -> readers | file in DATA/cc/commits | [storage](../system/storage.md) |
| `execution-v1.schema.json#freeze_result` | Call | [step_id](../system/records.md#term-step-id) to Binding refs plus batch ref | freeze (M03) -> launcher, supervisor | in-process Python call | [toolchain](../capsule/toolchain.md) |
| `execution-v1.schema.json#workflow_start_args` | Call | Args to start the generic [SwarmFlow](../system/integration.md#term-swarmflow) script for one phase | supervisor -> workflow script | in-process Python call | [runner](../capsule/runner-broker.md#swarmflow-backend-talking-to-the-engine), [lifecycle](../system/lifecycle.md) |
| `execution-v1.schema.json#run_phase_started` | Record | Freeze 1 (prep) and freeze 2 (planned) record | supervisor -> store | put_system, durable record | [records](../system/records.md), [lifecycle](../system/lifecycle.md) |
| `execution-v1.schema.json#dispatch_reservation` | Record | Reserved dispatch identity before any effect | supervisor, runner -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#release_record` | Record | Release that lets successors run | supervisor -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#human_review_record` | Record | Attributable human review reply | terminal adapter -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_lifecycle` | Record | Append-only lifecycle transition | supervisor -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_planning_reserved` | Record | Planner call reservation | supervisor -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_model_call_reserved` | Record | Model call reservation | supervisor -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_rsi_session` | Record | RSI controller session state | offline controller -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_rsi_trial` | Record | Immutable RSI trial [snapshot](../capsule/library.md#term-library-snapshot) | offline controller -> private store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_rsi_security_clearance` | Record | Human request to clear a security latch | terminal -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_oracle_session` | Record | Private oracle session | [fixture oracle](../capsule/fixture-oracle.md#term-fixture-oracle) -> private store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_oracle_closure` | Record | Oracle closure and ablation schedule | fixture oracle -> private store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_oracle_result` | Record | Redacted aggregate oracle result | fixture oracle -> private store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_oracle_security_block` | Record | Oracle security latch | fixture oracle -> private store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_oracle_security_clearance` | Record | Oracle latch clearance | fixture oracle -> private store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_oracle_quota` | Record | Oracle query quota reservation | fixture oracle -> private store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_rsi_attempt` | Record | RSI attempt entry | offline controller -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record_activation` | Record | Library activation | librarian -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#system_record` | Record | Union of all system record kinds | any writer -> store | put_system, durable record | [records](../system/records.md) |
| `execution-v1.schema.json#call_descriptor` | Helper | Prompt of the SwarmFlow agent() call: [decl_hash](../capsule/fields.md#term-decl-hash), input refs, step_id | workflow script -> [CcBackend](../capsule/runner-broker.md#term-ccbackend) | in-process Python call (agent prompt) | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#runner_request` | Call | call, cancel or status for one dispatch | supervisor -> runner | length-prefixed JSON frames, authenticated local channel | [lifecycle](../system/lifecycle.md), [runner](../capsule/runner.md) |
| `execution-v1.schema.json#runner_response` | Call | State and committed Observation ref | runner -> supervisor | length-prefixed JSON frames, authenticated local channel | [lifecycle](../system/lifecycle.md) |
| `execution-v1.schema.json#runner_event` | Event | Proposed relay of a cc.* event to the supervisor bus | runner -> supervisor | length-prefixed JSON frames, authenticated local channel | [observability](../system/observability.md) |
| `execution-v1.schema.json#step_envelope` | Helper | Per-step envelope returned by agent() | CcBackend -> engine -> script | in-process Python call | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#tool_host_frame` | Frame | Frames between the runner and a tool-kind child (call, nested, model, result, errors) | runner <-> tool host | length-prefixed frames on the inherited socket | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#skill_turn_frame` | Frame | Required model reply shape in a skill [turn](../system/model-bridge.md#term-model-turn) | model -> skill handler | model reply text (JSON object) | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#runner_turn_entry` | Helper | Per model turn record in Observation [ext](../schemas/common.md#term-ext).runner.turns | runner -> Observation | record field | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#model_client_call` | Call | M05 complete() call context and its mapping to model_bridge_request | runner broker -> model client (M05) | in-process Python call | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#model_client_reply` | Call | M05 reply or error and its mapping from model_bridge_result | model client (M05) -> runner broker | in-process Python call | [runner](../capsule/runner.md) |
| `execution-v1.schema.json#gate_request` | Call | gate(obs_ref) | CcBackend -> [Gate host](../capsule/gate-host.md#term-gate-host) | in-process Python call | [gate host](../capsule/gate-host.md) |
| `execution-v1.schema.json#gate_result` | Call | GateResult: verdict, normalized verdict, routing action | [Gate](../verification.md#term-gate) host -> CcBackend, supervisor | in-process Python call | [gate host](../capsule/gate-host.md) |
| `execution-v1.schema.json#halt_report` | Report | Halt report for human review or headless exit 3 | halt host -> human session, CLI | terminal session or stdout | [lifecycle](../system/lifecycle.md), [toolchain](../capsule/toolchain.md) |
| `execution-v1.schema.json#event_envelope` | Event | The cc.* events on the event bus | launcher, supervisor, runner, Gate host, halt host -> subscribers | in-process event bus | [observability](../system/observability.md) |
| `execution-v1.schema.json#evidence_manifest_ref` | Helper | Return of seal_execution | evidence collector -> runner, Gate host | in-process Python call | [storage](../system/storage.md) |
| `execution-v1.schema.json#execution_evidence` | Report | Complete stage evidence manifest | evidence collector -> Gate host, supervisor | in-process Python call | [storage](../system/storage.md) |
