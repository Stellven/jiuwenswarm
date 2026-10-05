---
id: contracts.index.library_rsi
type: index
level: detail
status: draft
provides: []
depends_on: []
---

# Index: library, admission, offline RSI, oracle, process, delivery, intake and intent-repair contracts

Schema file: [library-rsi-v1.schema.json](library-rsi-v1.schema.json). Imports shared definitions from [services-v1](services-v1.schema.json) and generated schemas under `exports/schemas/`. Fixtures: `fixtures/library-rsi-v1.json`. Definitions marked `x-internal` are true helpers (no message sends them by itself) and are exempt from [fixtures](../system/test-surfaces.md#term-fixture) and from this index.

| Schema def | Family | Message | Sender -> receiver | Transport | Described in |
|---|---|---|---|---|---|
| `library-rsi-v1.schema.json#admission_request` | Call | assess() request | librarian/CLI -> admission | in-process call (single-writer librarian) | [capsule/admission.md](../capsule/admission.md) |
| `library-rsi-v1.schema.json#admission_decision` | Record | provider decision, committed as the Verdict body | admission provider -> librarian | in-process call (single-writer librarian) | [capsule/admission.md](../capsule/admission.md) |
| `library-rsi-v1.schema.json#library_snapshot_request` | Call | [snapshot](../capsule/library.md#term-library-snapshot)() request | supervisor at launch -> librarian | in-process call (single-writer librarian) | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#library_snapshot_result` | Call | snapshot() reply | librarian -> supervisor | in-process call (single-writer librarian) | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#library_snapshot` | Record | Frozen LibrarySnapshot record | librarian -> store (read by planner, binder) | committed record | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#catalogue_request` | Call | catalogue() request | planner service -> librarian | in-process call (single-writer librarian) | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#catalogue_result` | Call | catalogue() reply | librarian -> planner service | in-process call (single-writer librarian) | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#activation_request` | Call | activate() request | developer CLI -> librarian | in-process call, developer CLI | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#activation_record` | Record | Activation [SystemRecord](../system/records.md#term-systemrecord) payload | librarian -> store | committed record | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#rsi_start_request` | Call | start_rsi() request | developer CLI -> [RSI](../rsi.md#term-rsi) controller | in-process call, developer CLI | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_status_request` | Call | rsi_status() request | developer CLI -> RSI controller | in-process call, developer CLI | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_stop_request` | Call | stop_rsi() request | developer CLI -> RSI controller | in-process call, developer CLI | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_submit_request` | Call | submit_rsi() request | developer CLI -> RSI controller | in-process call, developer CLI | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_resume_request` | Call | resume_rsi() request | developer CLI -> RSI controller | in-process call, developer CLI | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_session_result` | Call | RsiSessionResult reply | RSI controller -> developer CLI | in-process call, developer CLI | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_attempt_entry` | Record | [attempts](../system/lifecycle.md#term-attempt).jsonl hash-chained entry | RSI controller -> store | committed record | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_trial` | Helper | rsi_trial SystemRecord payload | RSI controller -> store (read by oracle) | committed record | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_security_clearance` | Helper | rsi_security_clearance SystemRecord payload | human terminal -> store (read by oracle) | committed record | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_verify_boundary_request` | Call | rsi.verify_boundary() request | developer CLI -> boundary verifier | in-process call, developer CLI | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_verify_boundary_report` | Report | boundary suite report | boundary verifier -> store | committed record | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#trial_ref` | Helper | private trial reference | RSI controller -> oracle | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_ref` | Helper | Private oracle record reference | oracle -> RSI controller | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_begin_request` | Call | begin_session() request | RSI controller -> oracle | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_status_request` | Call | status() request | RSI controller or custodian -> oracle | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_session_result` | Call | SessionResult reply | oracle -> RSI controller | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_evaluate_request` | Call | evaluate() request | RSI controller -> oracle | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_aggregate_result` | Call | AggregateResult reply | oracle -> RSI controller | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_close_request` | Call | close_session() request | RSI controller -> oracle | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_finish_close_request` | Call | finish_close() request | RSI controller -> oracle | authenticated local oracle service (socket) | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_final_request` | Call | evaluate_final() request | custodian terminal -> oracle | authenticated local oracle service (socket), custodian channel | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#oracle_clear_security_request` | Call | clear_security() request | human custodian terminal -> oracle | authenticated local oracle service (socket), custodian channel | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#poc_execute_request` | Call | execute_poc() request | benchmark [capsule](../capsule/capsule.md#term-capability-capsule) (via broker) -> process service | authenticated local service | [capsule/process-boundary.md](../capsule/process-boundary.md) |
| `library-rsi-v1.schema.json#poc_execute_result` | Call | execute_poc() reply | process service -> benchmark capsule | authenticated local service | [capsule/process-boundary.md](../capsule/process-boundary.md) |
| `library-rsi-v1.schema.json#measurement_request` | Call | measure_next request | generated harness -> measurement service | descriptor-bound local channel | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#benchmark_sample` | Helper | BenchmarkSample (harness stdout line) | measurement service -> harness -> stdout parser | local channel, then stdout | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#measurement_result` | Call | measure_next reply | measurement service -> generated harness | descriptor-bound local channel | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#measurement_evidence` | Report | MeasurementEvidence Artifact value | measurement service -> store | committed record | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#syntax_check_evidence` | Report | syntax_check() evidence file | syntax checker -> runner (Artifact) | committed record | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#deliver_request` | Call | deliver() request | supervisor -> delivery module | in-process call | [capabilities/delivery.md](../capabilities/delivery.md) |
| `library-rsi-v1.schema.json#publication_manifest` | Record | Publication manifest | delivery module -> store | committed record | [capabilities/delivery.md](../capabilities/delivery.md) |
| `library-rsi-v1.schema.json#deliver_result` | Call | deliver() reply | delivery module -> supervisor | in-process call | [capabilities/delivery.md](../capabilities/delivery.md) |
| `library-rsi-v1.schema.json#intake_request` | Call | launch() request | CLI or web entry -> intake module | in-process call / authenticated local API | [capabilities/extract-text.md](../capabilities/extract-text.md) |
| `library-rsi-v1.schema.json#intake_result` | Call | launch() reply | intake module -> entry adapter | in-process call | [capabilities/extract-text.md](../capabilities/extract-text.md) |
| `library-rsi-v1.schema.json#resource_snapshot_request` | Call | snapshot_resources() request | intake or freeze_resources -> supervisor snapshot service | in-process call | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#resource_snapshot_result` | Call | snapshot_resources() reply | supervisor snapshot service -> caller | in-process call | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#intent_fidelity_review` | Report | fidelity review of a compiled intent | [research.verifier](../capsule/gate-capsules.md#term-verifier) (profile research.accept_intent.v1) -> research.compile_intent | nested capsule call result | [capabilities/intent-compile.md](../capabilities/intent-compile.md) |
| `library-rsi-v1.schema.json#intent_repair_record` | Report | bounded repair record | research.compile_intent -> store | committed record | [capabilities/intent-compile.md](../capabilities/intent-compile.md) |
| `library-rsi-v1.schema.json#check_run` | Helper | One check that actually ran (id, runner hash, pass, fail or unknown) | admission -> Verdict body | in process | [capsule/admission.md](../capsule/admission.md) |
| `library-rsi-v1.schema.json#library_entry` | Helper | One selected capability in a library snapshot or catalogue | librarian -> snapshot readers | store | [capsule/library.md](../capsule/library.md) |
| `library-rsi-v1.schema.json#trial_file` | Helper | One file of a private RSI trial (path, hash, content ref) | controller -> oracle | private evidence root | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#rsi_state` | Helper | State of an offline RSI session (preparing, running, closing, closed, stopped, blocked, finished, no_candidate) | RSI controller -> readers | store | [capsule/rsi-engine.md](../capsule/rsi-engine.md) |
| `library-rsi-v1.schema.json#attempt_disposition` | Helper | Comparison outcome of one attempt (kept, rejected, promotable, no_candidate) | oracle -> controller | private authenticated socket | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#sample_values` | Helper | Named numeric values of one benchmark sample | measurement service -> harness | descriptor-bound local channel | [capabilities/measurement-protocol.md](../capabilities/measurement-protocol.md) |
| `library-rsi-v1.schema.json#evaluator_manifest` | Record | Private manifest: oracle code, launcher, guard and scoring-rule hashes, split hashes, loop and [final set](../capsule/fixture-oracle.md#term-hidden-final-set) refs, model pins, minimum counts | custodian -> oracle | [private oracle](../capsule/fixture-oracle.md#term-fixture-oracle) store | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#fixture_set_manifest` | Record | Metadata of one sealed fixture set (role, case count, lineage groups, per-case hashes, set hash, headroom evidence; no case content) | custodian -> oracle | private oracle store | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#planted_child_manifest` | Record | The fixed planted-child corpus: at least 10 known-bad and 3 known-good child hashes with expected disposition | custodian -> oracle | private oracle store | [capsule/fixture-oracle.md](../capsule/fixture-oracle.md) |
| `library-rsi-v1.schema.json#rsi_attack_scenario` | Record | One violation-suite scenario: id RSI-S01 to RSI-S24, attack, expected refusal and [reason code](../schemas/policy.md#term-reason-code) | RSI engine -> boundary verifier | in process | [capsule/rsi-attacks.md](../capsule/rsi-attacks.md) |
| `library-rsi-v1.schema.json#rsi_attack_result` | Helper | Result of one scenario run: observed PASS, FAIL or [NOT_RUN](../decisions.md#term-not-run), reason code, evidence refs | boundary verifier -> rsi_verify_boundary_report | in process | [capsule/rsi-attacks.md](../capsule/rsi-attacks.md) |
