---
id: cap.measurement-protocol
type: reference
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.measurement_protocol, compare_to_thresholds, freeze_resources, syntax_check, system.measurement_service]
consumes: [cc.type.hypothesis_blueprint, cc.type.benchmark_payload, cc.type.evaluation_verdict]
depends_on: [../types/hypothesis-blueprint.md, ../types/benchmark-payload.md, ../types/evaluation-verdict.md, ../system/storage.md]
tags: [m1, measurements, contract]
level: detail
prd: [3.5.2, 3.7.2, 3.7.3, 3.8.4, 4.2.4, 4.9.4]
---

# Measurement, compiler and resource contracts

PRD: 3.5.2, 3.7.2, 3.7.3, 3.8.4, 4.2.4, 4.9.4

> Answers: Which measurement methods, sample stream and compiler checks are shared by Hypothesis, POC, Benchmark and Evaluation?

This page is the home of the technical protocol shared by Hypothesis, Builder, Benchmark and Evaluation. Scientific classification is defined by the [frozen](../system/lifecycle.md#term-freeze) Blueprint rule and Evaluation contract. Trusted measurement implementations are registered separately. Proposed code lives in `cc/measurements/registry.py`, `cc/measurements/protocol.py` and ordinary helper modules. The registry/checks are independently authored; [RSI](../rsi.md#term-rsi) and generated code cannot change them.

## Frozen methods

`resolve_method(method_id, method_sha256) -> MeasurementMethod` resolves a committed registry entry with ID, raw unit, allowed comparison bases, code and configuration schema hashes, Python entry point, hardware requirements and supported statistics. The method validates the frozen benchmark configuration before Hypothesis can pass its [Gate](../verification.md#term-gate). Missing methods are `INPUT_INCOMPLETE`; no model-written replacement is accepted. Methods measure live arm outputs; fixture expected answers never become a measurement method.

Schema for the trusted [snapshot](../capsule/library.md#term-library-snapshot) service that `freeze_resources` calls (and that [storage](../system/storage.md) names `snapshot_resources(intake_ref, resource_ids)`): `library-rsi-v1.schema.json#resource_snapshot_request` and `library-rsi-v1.schema.json#resource_snapshot_result`. `freeze_resources` is the capsule-facing [operator](README.md#term-operator); it resolves the baseline and dataset resource ids and passes them as `resource_ids`.

`freeze_resources(intake: intake, baseline_resource_id: id, dataset_resource_id: id, benchmark_config: file) -> snapshots: collection<resource_snapshot>` requests the trusted snapshot service. Each [`resource_snapshot`](../types/resource-snapshot.md) names the immutable manifest, content hash, [kind](../capsule/capsule.md#term-capsule-kind) and read-only authority used by the blueprint. The service [checks](../capsule/fields.md#term-check) resource kinds, readable non-symlink trees, config schema and registered hardware. One supervisor [batch](../system/storage.md#term-commit-batch) publishes all manifests, copied read-only resources and config before returning. Missing resources reject before code generation. Identical source hashes/config return identical content; changed input requires a new run. The [capsule](../capsule/capsule.md#term-capability-capsule) has no authority to snapshot arbitrary host paths. Source paths are resolved from authorized intake, as specified by [storage](../system/storage.md).

## Harness stream: `BenchmarkSample`

The harness [runs](../system/lifecycle.md#term-run) one declared experiment, with baseline immediately followed by treatment for each repeat. Seed for repeat i is blueprint.seed+i for both arms, with every seed in [0,4294967295]. Unsupported method seed domains or overflow are rejected during registration. Use the same frozen data, configuration and device. Isolate baseline and treatment state according to the registered method; never apply the patch to the immutable baseline snapshot.

Schema: `library-rsi-v1.schema.json#benchmark_sample`. Each stdout line is a closed UTF-8 JSON object: `{protocol_version: 1, arm: baseline|treatment, repeat_index: integer, seed: integer, values: map<metric_id, finite number>, measurement_ref: Ref(artifact)}`. Only registered metric IDs are allowed. Order is baseline(0), treatment(0), baseline(1), treatment(1), and so on. Diagnostics go to stderr. A complete stream contains exactly 2*repeats samples. Duplicate arms, extra samples, missing mandatory metrics, non-finite numbers, wrong seeds, malformed JSON or protocol version reject the stream with `MEASUREMENT_PROTOCOL_ERROR`; preserve the original bytes. Reject invalid UTF-8, duplicate JSON keys, unknown object/metric keys, blank lines and incorrect order with MEASUREMENT_PROTOCOL_ERROR. A final newline is optional; all preceding records require one LF delimiter (CRLF accepted by normalizing only line delimiters). Every blueprint metric is mandatory in M1. Partial samples remain failure capture in [Observation](../schemas/observation.md#term-observation), not a success-shaped [benchmark_payload](../types/benchmark-payload.md#term-benchmark-payload). The trusted parser derives benchmark_payload only after matching every sample to its authoritative measurement_ref.

Use canonical decimal arithmetic at precision 28 with round-half-even; mean is sum/count, median is the middle sorted value or mean of the two middle values, minimum/maximum use observed values. Equality is exact on these canonical rounded numbers, with no hidden tolerance. Non-finite/overflow results reject with MEASUREMENT_PROTOCOL_ERROR. Aggregate each metric across all required repeats using its frozen statistic. Let b and t be baseline and treatment aggregates. Benchmark stores raw `delta=t-b`. Evaluation alone transforms:

| Basis | Comparison value | Preconditions |
|---|---|---|
| absolute | t | Unit remains the raw unit |
| delta | t-b | Unit remains the raw unit |
| relative_percent | 100*(b-t)/abs(b) for lower; 100*(t-b)/abs(b) for higher | b must be nonzero; beneficial change is positive |
| percentage_points | 100*(t-b) | Both raw values are fractions in [0,1]; output unit is percentage points |

Zero denominators or missing samples produce a null comparison and explicit incomplete evidence, never division by zero, a zero improvement or an invented value. Missing mandatory evidence [blocks](../system/modules.md#term-block) infrastructure release; Evaluation records its validity blocker without treating it as scientific rejection. Comparators have their ordinary numeric meaning (`lt`, `lte`, `gt`, `gte`, `eq`), applied separately to expected, acceptance and falsification predicates. No downstream code chooses a unit or comparator.

`compare_to_thresholds(benchmark_payload, hypothesis_blueprint) -> comparisons: file` is an ordinary pure fixed helper. Its file is canonical JSON of the comparison entries owned by [evaluation_verdict](../types/evaluation-verdict.md#term-evaluation-verdict); it is not a new hand-maintained schema. The [work capsule](README.md#term-work-capsule) combines these entries with its single plausibility [turn](../system/model-bridge.md#term-model-turn) and the pre-registered Blueprint classification rule. Missing preregistered Blueprint rule yields INPUT_INVALID before evaluation. Gate independently recomputes arithmetic and policy output.

## Syntax checking

`syntax_check(patch: file, harness: file, blueprint: hypothesis_blueprint) -> evidence: file` runs the fixed compiler and AST scanner in the restricted syntax profile. Schema: `library-rsi-v1.schema.json#syntax_check_evidence`. Evidence is a closed object `{protocol_version:1, patch_sha256, harness_sha256, compiler_exit_code, ast_checks:[{id,result:pass|fail,message}], stdout_sha256, stderr_sha256}`. The runner publishes it as an Artifact and provides its Ref to the POC producer. Compile without importing or executing generated modules; compiler writes only disposable bytecode. Scan forbidden imports, mutation of frozen methods/resources, and conformance to the registered logging adapter. Static scanning supports confinement; it is not proof of safety or runtime measurement success. One failed check returns evidence and [halts](../system/lifecycle.md#term-halt) at the POC Gate; no repair loop runs.

These operators inherit the runner's pinned dependency validation, deadline, cancellation and duplicate-call rules. File writes use the store/broker, not arbitrary capsule filesystem access. [Verification](../system/test-surfaces.md) supplies independent parser, snapshot, compiler and comparison invocation points; no runtime execution is claimed here.

## Trusted measurement authority

Schema: `library-rsi-v1.schema.json#measurement_request` (request), `library-rsi-v1.schema.json#measurement_result` (reply, carrying a `library-rsi-v1.schema.json#benchmark_sample` or a denial reason) and `library-rsi-v1.schema.json#measurement_evidence` (committed Artifact value). MeasurementRequest is the closed `{protocol_version:1, operation:measure_next, request_id:id}` on a descriptor bound to a reserved POC request. Identical request IDs return the same committed sample; new IDs advance exactly one position in the fixed schedule. A request after the final sample is denied. The connection's run/blueprint capability cannot be supplied or rebound by the harness. Snapshot and syntax operators are [idempotent](../contracts/principles.md#term-idempotency) with internal snapshot/compiler scopes only; compare_to_thresholds is pure. Caller declarations pin these operator versions and publish their permitted effects.

The generated harness is not an authority for metric numbers. `cc/security/measurement_service.py` runs trusted registered methods in a supervisor-controlled measurement process, with an authenticated descriptor-scoped request channel. A generated harness may call only `measure_next()` for its reserved POC request; it supplies no values, arm, seed, dataset, entrypoint, method code or config. The service schedules the next frozen baseline/treatment repeat, resolves all pins from the run's admitted blueprint, and invokes the registered method's fixed workload adapter. Baseline uses immutable original code; treatment applies only the admitted patch in a disposable child. The trusted method independently obtains host instrumentation or computes scientific metrics from captured workload results according to its pre-registered code. A method that merely trusts workload-supplied scalar scores cannot satisfy provenance and is rejected at registration.

For each arm the service commits a closed MeasurementEvidence Artifact `{protocol_version:1, poc_request_id, blueprint_ref, resource_snapshot_sha256, benchmark_config_sha256, method_hashes:map<metric_id,sha256>, arm,repeat_index,seed,values,workload_capture_refs:list<Ref(artifact)>}`. The artifact type is base json with this service-owned value schema; no capsule-to-capsule wire uses it. It returns the canonical BenchmarkSample and its measurement_ref to the harness (as `measurement_result.sample`), which forwards it to stdout. Evidence writer identity and authenticated request binding establish authority; a checksum of invented stdout is insufficient. The parser and Gate verify exact equality with these records, invocation/capture of both arms, and the registered method pins. A forged value or replayed other-run ref fails even with valid JSON.

The service has no model/oracle credentials, hidden RSI answers or general host-writing permission. It receives only the run snapshot, approved methods and disposable workload directories. Failure/cancellation terminates its workload tree and retains partial evidence. Issue 58 keeps unsupported measurement methods blocked; these authority rules apply to every future method without choosing its internal measurement algorithm.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is BLOCK, [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.measurement-protocol.AC-01 | PRD 3.7.2 | A stream with duplicate arms, extra or missing samples, non-finite numbers, wrong seeds, malformed JSON or a wrong protocol_version is rejected with MEASUREMENT_PROTOCOL_ERROR. | BLOCK |
| cap.measurement-protocol.AC-02 | PRD 3.7.2 | Seed for repeat i is blueprint seed + i for both arms and lies in [0, 4294967295]; overflow is rejected at registration. | BLOCK |
| cap.measurement-protocol.AC-03 | PRD 3.8.4 | Transform fixtures: relative_percent with zero baseline and percentage_points outside [0,1] give null comparison plus incomplete evidence; no division by zero and no invented zero improvement. | BLOCK |
| cap.measurement-protocol.AC-04 | PRD 3.7.3 | Decimal arithmetic at precision 28, round half even, gives exact expected values on fixtures; equality has no hidden tolerance. | BLOCK |
| cap.measurement-protocol.AC-05 | PRD 3.7.3 | A harness emitting plausible invented values, a forged or replayed measurement_ref, or a wrong arm, seed, method or config is rejected even when sample JSON is valid. | BOUNDARY |
| cap.measurement-protocol.AC-06 | PRD 3.7.3 | An identical measurement request id returns the same committed sample; a request after the final sample is denied. | BOUNDARY |
| cap.measurement-protocol.AC-07 | PRD 3.5.2 | freeze_resources publishes all manifests, read-only copies and config in one batch; a missing resource or a symlink tree rejects before code generation. | BOUNDARY |
| cap.measurement-protocol.AC-08 | US-11 | The measurement service holds no model credentials and no hidden fixtures; killing it mid-measurement returns no complete sample and keeps partial evidence. | SYSTEM |
