# Feature Specification: M0-001 — standalone whole Intent Compiler
**TASK**: [M0-001 TASK](TASK.md)
**Parent TASKS**: [M0 register](../TASKS.md)
**Revision / date**: r1 / 2026-10-08
**Feature Branch**: `ai4r_test_with_spec_kit`; no branch creation or switch.
**Input**: Supplied PRD Main §4.7; relevant PRD Context §§1.4,2,3.1,3.2,4.1–4.3,4.5–4.6,5,6.5; Architecture Main completion/node/foundation/browser/proof sections; Architecture Context required dependency documents and current catalog; benchmark contract items 1–4. Exact clause allocation and per-file source identity are in [TASKS](../TASKS.md#3-source-coverage-allocation) and [source-baseline.json](source-baseline.json).
**Status**: Specified; this is not a runtime acceptance result.

## User Scenarios & Testing

### User Story 1 — receive a faithful, verified research contract (Priority: P1)
An authorized researcher supplies an actionable research request and permitted local materials. The component captures exact sources, interprets the user's meaning, verifies that interpretation, compiles obligations and releases a verified Research Brief. The researcher can distinguish their stated values from protected defaults and inspect how every decision was made.

**Independent Test**: Submit the frozen actionable request with supported documents through the ordinary authenticated client and an actual approved configured model. Observe four bounded work/review calls, intermediate Intent acceptance, Requirements acceptance and enclosing-node durable release. Retrieve the named Brief and evidence, and have the bounded consumer accept that exact released Brief.

**Acceptance Scenarios**:
1. Given an actionable objective, authorized workspace, supported sources and ready execution prerequisites, when compilation runs, then accepted Intent precedes Requirements and an exact verified Brief2 is durably published only after the node decision commits.
2. Given an actionable request missing optional hardware/method/numeric targets, when compilation runs, then purpose and qualitative targets remain source-grounded, the only applicable authorized missing-parameter default is explicitly attributed, and no experimental protocol or numeric threshold is invented.
3. Given declared mandatory outcomes, exclusions, preferences, resources and compute bounds, when the Brief is compiled, then they remain correctly separated and traceable with resolved acceptance/evidence obligations.

### User Story 2 — see why a request or invocation halted (Priority: P1)
An authorized user receives a visible attributable halt for unusable intent, conflicting instructions, malformed output, unavailable environment, exceeded bounds or failed storage. Candidate artifacts and actual checking evidence remain inspectable. The component does not invent corrected work or continue silently.

**Independent Test**: Run the frozen negative cases for topic-only intent, contradiction, unsupported additions, lost Brief constraints, malformed producer/assessor output, stale subject, missing criteria/evidence, model no-output/timeout and storage failure. Assert no successor dispatch or external release after the failed boundary.

**Acceptance Scenarios**:
1. Given a topic without discernible purpose/result, when valid-shape Intent is produced, then independent usability review blocks and Requirements never runs.
2. Given a structurally valid but invented method/target or contradictory mandatory constraints, when it is checked, then semantic findings identify the source/field failure and the protected gate halts without rewriting the artifact.
3. Given invalid work JSON or no output, when deterministic checking runs, then the unnecessary verifier is not dispatched; a real failure receipt is retained with empty absent-output inventory.
4. Given an overall verifier PASS with missing/duplicate findings, swapped subject/context or absent evidence, when the host validates it, then no accepted reference is published.
5. Given a passed assessment but failed durable commit, when release is attempted, then readiness stays blocked and the visible error does not claim that missing evidence persisted.

### User Story 3 — operate and independently inspect the compiler (Priority: P1)
An authenticated browser or headless benchmark client checks target/readiness, submits a uniquely identified request, reconciles uncertain transport, observes status, cancels and exports successful or failed evidence through the same ordinary boundary. The client has no gate-state or credential authority.

**Independent Test**: Exercise readiness, submission, request-ID reconciliation, status, retrieval and cancellation over the real local service. Repeat the same request ID after transport loss and confirm one run. Verify authorized scope and reject unauthenticated/cross-workspace operations.

**Acceptance Scenarios**:
1. Given an unavailable model/store/required enforcement prerequisite, when readiness is queried, then liveness and execution readiness are distinct and submission is explicitly rejected or halted under the appropriate structured reason.
2. Given a transport interruption after submission, when the client reconciles its ID, then it finds the existing run without duplicate model work.
3. Given a terminal halt, when a headless client waits finitely and retrieves evidence, then it returns non-success without asking for human approval and retains the available bundle.
4. Given a successful, failed or blocked attempt, when authorized export is retrieved, then the versioned manifest names original/qualified inputs, candidate/accepted records, exact contracts/pins, profiles/results/assessments/decisions, actual observations/configuration and explicit missing evidence.

### User Story 4 — retain accountable work across browser and image lifecycle (Priority: P1)
An operator launches the packaged component without a separate frontend startup helper. Browser inspection agrees with stored/exported records. Browser closure leaves server-owned work running; cancellation prevents further dispatch; image restart preserves evidence and pauses interrupted work without replay.

**Independent Test**: Start the bundled image on host loopback, exercise same-origin browser/API, disconnect/reconnect, cancel a bounded invocation, recreate with the same volumes, and inspect existing records. Verify denied unauthenticated/LAN access and no model-adapter listener exposed to clients.

**Acceptance Scenarios**:
1. Given the packaged image and protected approved configuration, when its entrypoint starts, then the browser and API are available together on the documented loopback endpoint, or an explicit prerequisite failure is inspectable.
2. Given an active run, when the browser closes, then the run continues under server ownership; reconnection reads the same run.
3. Given cancellation, when it is acknowledged, then no successor dispatch occurs and known/unavailable effects remain visible.
4. Given an interrupted run and persisted volumes, when the application restarts, then historical accepted/candidate records remain inspectable and unfinished work is paused without retry or replay.

### User Story 5 — assess this exact measured trial (Priority: P1)
The trial executor can establish which required behavior actually passed on the current uncommitted candidate, which live prerequisites remain blocked, and which model quality outcomes were observed. Spec Kit diagnostics and work checkboxes never substitute for runtime proof.

**Independent Test**: Check the native AC-to-evidence matrix, raw command outputs, candidate hashes, frozen fixture/profile identities, analysis/remediation history and token/cost JSON. Every PASS must point to executed current evidence; required skips/unavailable model/image prerequisites remain non-PASS.

**Acceptance Scenarios**:
1. Given frozen labelled model cases and an actual endpoint, when evaluation runs, then per-case judgments, false acceptances/refusals, sample counts, prompts/settings, timing/calls and provider/telemetry limitations are retained without inventing a reliability rate from a single response.
2. Given generated spec/plan/tasks, when analyze finds a material gap, then authoritative artifacts are corrected before coding; after implementation, converge findings become remediation tasks with affected checks rerun.
3. Given unavailable token/cost accounting, when the required JSON report is updated, then values remain null/unavailable with a reason and are never guessed or reported as zero.

### Edge Cases
- Empty request; missing/unauthorized/unreadable directory; configured empty default docs directory; empty/unreadable/oversized/unsupported required input; malformed or encrypted/unextractable PDF; undecodable text; traversal/symlink escape; swapped content after qualification.
- CRLF and Unicode/non-BMP source text with exact end-exclusive code-point spans; out-of-bounds spans, duplicate local IDs, unpermitted refs and unresolved obligation IDs.
- Optional missing method/hardware/numeric target versus blocking missing requested work; contradiction versus uncertain scientific success; untrusted instruction injection in request/documents/candidate text.
- Invented objective/method/percentage, silent preference promotion, lost exclusion/constraint/resource, unauthorized default or assumption pointer to a nonexistent field; baseline-relative factors versus absolute target values and units.
- Malformed producer/assessment, wrong version, stale/swapped subjects or contexts, missing/duplicate criterion, inconsistent overall verdict, unavailable evidence, no output, denied effect, unsupported mandatory enforcement or stale admission.
- Cyclic internal dependencies; node/subnode identity mixup; multiple CC bindings; authority pooling; changed declaration/dependency/configuration; child or aggregate call/time overrun; unavailable token/memory measurements.
- Model unavailable/unauthenticated, owned-process timeout/cancel, unsupported seed, provider identity known only from configuration; no hidden retry/cache/model substitution.
- Artifact/state persistence failure; transport loss after run creation; repeated ID with different payload; restart interruption; cancellation after observed effects; browser disconnect; export path/audience escape and redaction identity.
- Unsupported consumer Brief version, candidate Brief and uncommitted node release; container daemon/image prerequisites absent. Distributed/concurrent-run orchestration and downstream scientific execution are excluded, so their cases are N/A by scope rather than silently skipped.

## Requirements

### Functional Requirements
- **FR-001**: Qualify only authorized supplied local txt/md/pdf documents and registered project/data resources; deterministically reject required invalid inputs and preserve exact provenance. Source: PRD Context §§3.1.1–3.1.5; Architecture Main intake; field-catalog qualified-intake/resource-snapshot.
- **FR-002**: Preserve exact original bytes and decoded/extracted text separately, Unicode span basis, hashes, resource roles and qualification reasons. Source: Architecture Context Source precedence; intent-and-requirements Intent IR; benchmark item 2. Explicit hashing exception recorded in TASK/register.
- **FR-003**: Produce versioned source-attributed Intent1 capturing purpose/result/context/scope/constraints/preferences/targets/uncertainty with readiness as candidate data. Source: PRD §4.7.2–4.7.3; intent-design Intention responsibility; critical Intent schema.
- **FR-004**: Independently assess exact submitted Intent for fidelity, coverage, consistency and usable purpose/result; block topic-only, contradictory/invented interpretations without Requirements dispatch or repair. Source: intent-design Intent verifier/Gate; compiler-verification.
- **FR-005**: Compile Brief2 only from accepted Intent and permitted context/defaults, preserving all mandatory/preferences/constraints/input resources/user targets/deliverables/acceptance/evidence obligations with resolved identities. Source: PRD §4.7.5, Context §3.2; Research Brief schema/fields.
- **FR-006**: Apply only protected authorized missing-parameter defaults with actual affected-field pointers; preserve qualitative omissions and typed quantitative constraints without selecting experimental method/protocol or inventing intent. Source: PRD §4.7.3–4.7.4; reference Intent/Brief defaults/metrics.
- **FR-007**: Assign protected checking profiles before producer output; execute complete deterministic checks first, then separate bounded read-only verifiers, and mechanically validate exact subject/context/evidence and every required criterion exactly once. Source: guard-design; checking; compiler-verification Independent criteria.
- **FR-008**: Protected host gates alone decide advancement and durable exact acceptance; aggregate required work/verifier evidence, both subnode decisions and node budgets with no extra semantic call. Source: checking Gate decision/Subnode versus node release; Main completion boundary.
- **FR-009**: Admit/pin actual shipped supported declarations, implementations, dependency closure and independently owned checking assets; bind one CC per work/verifier subnode with explicit node2/subnode1 identities/ports and intersected authority. Source: capsule/declaration; capsules; node-execution.
- **FR-010**: Use approved protected audited model access, distinct producer/verifier invocation contexts and frozen endpoint/configuration; retain protected Codex fallback interface without retries, replay, cache substitution or hidden switching. Source: model-routing; placement; Main foundations.
- **FR-011**: Enforce effective scope/time/call/effect bounds before and during dispatch; observe actual route/pins/results/errors/timing/calls and truthful available token/cost/hardware enforcement facts. Unavailable mandatory enforcement blocks. Source: PRD §4.7.4; model-routing; compiler-verification.
- **FR-012**: Capture immutable named artifacts and authoritative durable acceptance/run-state; persistence failure blocks release and retains only actually saved evidence. Source: placement Data foundation; checking; artifact-inspection.
- **FR-013**: Cancellation stops new dispatch and contains owned active work; browser disconnect does not cancel; restart pauses interrupted attempts without replay and retains history. Corrected input starts fresh linked work. Source: failure-and-human; Main browser boundary.
- **FR-014**: Protect authenticated user/account/profile/workspace scope, credentials/configuration and control state; readiness exposes exact instance/build/interface/schema/profile and explicit prerequisite availability. Source: benchmark item 1; automation; placement; field-catalog client-readiness.
- **FR-015**: Provide idempotent unique-ID submission/reconciliation, correlated status/candidate-versus-accepted/gate reasons, finite non-success headless outcomes, authorized cancel and evidence retrieval through one ordinary client boundary. Source: benchmark items 2–4; automation; client fields.
- **FR-016**: Export all required input/artifact/contract/admission/profile/check/assessment/decision/observation/configuration/usage evidence for successful/failed/blocked runs through a versioned named manifest, with exact hashes and explicit missing/redacted entries. Source: benchmark item 4; artifact-inspection; runtime field contracts.
- **FR-017**: Provide browser submission/status/inspection/download from the same records; bundle built frontend/service/runtime in one image with own entrypoint, same-origin API and host loopback-only publication, durable mounted evidence and protected model access. Source: Main Browser boundary; automation/placement startup.
- **FR-018**: Demonstrate bounded consumer compatibility on the exact released Brief2 and reject candidates/unsupported versions without implementing downstream stages. Source: Main Required proof; compiler-verification.
- **FR-019**: Freeze labelled expectations and profiles before real-model measurements, preserve per-case outcomes/false acceptances/refusals/provider limitations, and distinguish fixture representation checks from semantic model quality. Source: compiler-verification; guard-design calibration; VERIFICATION §8.
- **FR-020**: Retain exact candidate/source/interface/fixture/environment/command/expected/observed/raw evidence in native correspondence; execute analyze before coding and converge/remediation after implementation; maintain truthful mandatory coding token/cost report. Source: Code_prompt; SOP/VERIFICATION and user instructions.

### Key Entities
- Qualified intake2: authorized exact request/extracted references, resource registrations and explicit rejections.
- Immutable Ref/source span: exact content hash/ID and Unicode code-point range in separately identified source text.
- Intent1 and Brief2: attributable intermediate interpretation and released downstream research obligation contract.
- Capsule declaration/admission/dependency pins; node2/subnode1; bound check plan2/profile/policy/configuration: protected frozen eligibility, assignment and authority.
- Deterministic result1, verifier assessment1, gate2, accepted-output2: observed checks, read-only findings, protected control decision and durable exact release.
- Invocation observation2/model-route1: actual call/effects/configuration/timing/telemetry, including explicit unknown values.
- Client readiness/submission/status/retrieval/cancellation/error1 and Run Bundle1: ordinary authenticated operations and named evidence. Normative agreement semantics remain in [TASK §4](TASK.md#4-embedded-cross-module-agreements).

## Success Criteria

### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD Context §§3.1.1–3.1.5; FR-001; stories 1–2 | Authorized nonempty request and permitted readable default/specified directories qualify; supported txt/md/pdf and project/data roles register; every invalid required input rejects with named reason before model dispatch. Empty authorized default docs directory is allowed. | BLOCK, BOUNDARY |
| AC-002 | Architecture Intent fields; benchmark item 2; FR-002 | Every qualified source retains exact bytes/hash and separately identified text; CRLF/non-BMP spans use end-exclusive Unicode code points; swaps, unpermitted refs and span/size/path escape fail. Resources remain separate from reasoning text. | BLOCK, BOUNDARY |
| AC-003 | PRD §4.7.2–4.7.3; Intent schema; FR-003 | Intent is exact version1 with every required field, unique IDs, resolvable permitted refs and valid nonempty spans; candidate readiness alone cannot dispatch Requirements. | BLOCK, BOUNDARY |
| AC-004 | intent-design Intent verifier; FR-004; story 1 | Submitted actionable Intent passes only with complete source-grounded fidelity/coverage/consistency/usability findings; purpose/result are sufficient without scientific solution selection. Real-model evidence is required for semantic completion. | BOUNDARY, SYSTEM |
| AC-005 | compiler-verification topic/contradiction/invention; FR-004; story 2 | Frozen topic-only, contradictory and unsupported confident interpretation cases halt semantically even when shape validates; zero Requirements dispatch after blocked Intent; no artifact rewrite/retry. | BLOCK, BOUNDARY, SYSTEM |
| AC-006 | PRD §4.7.5/Context §3.2; Brief schema; FR-005 | Brief version2 contains all required obligations/inputs/resources/confirmation fields; IDs are unique and metric/acceptance/evidence links resolve; Requirements input is the exact durably accepted Intent. | BLOCK, BOUNDARY |
| AC-007 | PRD §4.7.3–4.7.4; Brief default/constraint fields; FR-006 | Preserve user constraints, exclusions, mandatory/preferences and qualitative/numeric target semantics; only authorized parameter defaults apply with policy source and existing pointer. Missing hardware may default single_gpu without claiming availability. Lost obligations, fabricated purpose/method/percentage/default or protocol fail. | BLOCK, BOUNDARY, SYSTEM |
| AC-008 | guard-design/checking; FR-007 | Profiles/check plans pin obligations before output; every mandatory deterministic/semantic ID occurs exactly once with meaningful reason/resolved evidence. Bad work avoids verifier dispatch; malformed/stale/swapped/incomplete/contradictory assessments cannot advance; verifier has no replacement/control authority. | BLOCK, BOUNDARY |
| AC-009 | Main Completion/checking Gate2; FR-008 | Two work decisions and enclosing node decision use exact run/node/subnode/attempt/pins/subjects; protected host alone commits exact accepted refs. Node aggregation requires recorded work/review/internal acceptance and adds zero model calls. Non-advancing outcomes publish no external Brief. | BLOCK, BOUNDARY, SYSTEM |
| AC-010 | capsule/declaration/capsules/node-execution; FR-009 | Actual shipped declarations/implementation/dependencies/check profiles admit under validated supported eligibility; one CC per explicit subnode, exact ports/pins and authority intersection. Altered/stale admission, node/subnode swaps, cycles/multiple bindings/permission pooling reject. Synthetic fixture admission is not operational proof. | BLOCK, BOUNDARY |
| AC-011 | model-routing/placement/Main foundations; FR-010 | Real approved bridge executes separate bounded work/verifier invocations under frozen role/endpoint/context/owned access, captures actual requested/effective identity/error and retains protected fallback interface. No automatic retry, repair, cache/replay or hidden model substitution; protected credentials/IPC inaccessible to clients/capsules. | BLOCK, BOUNDARY, SYSTEM |
| AC-012 | PRD §4.7.4/compiler-verification; FR-011 | Frozen per-call/stage/node time/call bounds are enforced and aggregate includes verifier spend; violation/denied or unsupported mandatory effect/resource enforcement blocks new dispatch/release. Available actual calls/time/tokens/cost/effects/hardware readiness are observed; unavailable values remain null/reasons, never zero claims. Numeric safety bounds are plan configuration, not invented product SLAs. | BLOCK, BOUNDARY, SYSTEM |
| AC-013 | placement Data foundation/checking durable acceptance; FR-012 | Immutable candidate/decision/accepted record and authoritative state preserve exact identities. Required artifact/decision/state commit succeeds before accepted publication. Injected storage failure prevents release; no claimed persisted artifact absent on disk/state. | BLOCK, BOUNDARY, SYSTEM |
| AC-014 | failure-and-human/Main browser; FR-013 | Explicit cancel prevents subsequent dispatch, contains current owned work and preserves observed/unknown effects. Disconnect alone continues server work; restart retains evidence/accepted state and pauses interrupted work with zero replay. Fresh corrected work links rather than changes halted history. | BLOCK, BOUNDARY, SYSTEM |
| AC-015 | benchmark item1/client-readiness/placement; FR-014 | Readiness exposes build/instance/client and payload versions, supported compiler-only profile and auth/storage/model/required-enforcement states with reasons. Unauthenticated/wrong-target/version/profile or cross-account/workspace actions reject. Account/profile survives run/workspace lifecycle; credentials/control tokens excluded from prompts/exports. | BLOCK, BOUNDARY, SYSTEM |
| AC-016 | benchmark item2/client submission/reconciliation; FR-015 | Authenticated exact original input/approved configuration submission returns a run ID or structured rejection. Repeating/reconciling identical authorized client request ID creates exactly one run/model execution; differing input for the same ID rejects, including transport-loss recovery. | BOUNDARY, SYSTEM |
| AC-017 | benchmark item3/client status/cancel/error; FR-015 | Ordinary client exposes correlated monotonic status/stage, candidate/accepted refs, gate reasons and terminal outcome; cancellation is explicit and scoped. Headless wait is finite and returns non-success for halt/block/cancel/pause without human prompt; observed errors retain permitted evidence. | BOUNDARY, SYSTEM |
| AC-018 | benchmark item4/artifact-inspection/runtime fields; FR-016 | Authorized export for success/failure/block contains all mandated named exact input/artifact/contract/pin/config/profile/check/assessment/decision/invocation/release records and actual usage/effect/readiness observations. Every ref resolves to exact hash/type/version/path or explicit withheld/unavailable reason; changed redaction gets new hash; traversal/unauthorized audience rejects. | BLOCK, BOUNDARY, SYSTEM |
| AC-019 | Main Browser/artifact-inspection; FR-017 | Browser submits request/resources, observes stage/halt/defaults/uncertainty/gate reasons, distinguishes candidates/accepted records and inspects/downloads named files matching exports byte/meaning. Built frontend succeeds and representative browser user journey uses the actual client boundary. | BOUNDARY, SYSTEM |
| AC-020 | automation Local Compose/placement startup; FR-017 | One pinned application image entrypoint starts built UI/API/runtime without host frontend helper; browser/API same origin, host publication loopback-only, no public model adapter/control store. Image recreation preserves volumes/history; unavailable prerequisites are explicit. Startup/unauthenticated/LAN/credential and required enforcement boundary checks execute against actual deployment, otherwise BLOCKED. | BOUNDARY, SYSTEM |
| AC-021 | Main Required proof/benchmark completion; FR-018 | Bounded real consumer reads the exact published Brief2 with required fields/current node-release record; candidates, uncommitted refs and unsupported versions reject. Consumer does not implement downstream research. | BOUNDARY, SYSTEM |
| AC-022 | compiler-verification Cases/guard calibration/VERIFICATION §8; FR-019 | Frozen labelled actionable, omissions, topic, contradiction, invented interpretation and lost-constraint challenge expectations are exercised with actual configured model. All raw case outcomes and false acceptance/refusal counts, repetitions/seeds/settings/provider limitations persist; fixtures/mocks and one response cannot certify semantic reliability. No unsupplied quality-rate threshold is asserted. | SYSTEM |
| AC-023 | Code_prompt mandatory report/VERIFICATION; FR-020 | Every required verification row records exact current candidate/source/spec/plan/IF/fixture/config/environment, command/working directory, expected/observed result, exit/counts/raw evidence/limitations. Coding token/cost JSON records pre/during/post measured values or explicit unavailable reasons, including tests/fixes/retries. Required skip/BLOCKED/NOT_RUN/STALE never becomes PASS. | BLOCK, BOUNDARY, SYSTEM |
| AC-024 | Code_prompt analyze/converge; FR-020 | Generate registered spec/plan/tasks; run analyze and resolve material coverage/consistency findings in native authorities before coding. Run converge after implementation, append and finish in-scope remediation, rerun affected checks, and preserve diagnostic truth/current evidence without a reviewer/approval gate. | BLOCK, SYSTEM |

All required behavior and failures have AC coverage. Runtime verification is required for behavior changes. Native tasks must map every AC to implementation, check and evidence; completed checkboxes are not acceptance.

## Scope and Assumptions
- Included scope is this whole standalone compiler plus required governed foundations and compiler-only system verification. Output is released Research Brief2 or attributable terminal halt; intermediate Intent alone is not success.
- Excluded scope: existing app integration/imports, downstream DAG/research stages, advanced compilation/clarification/planning/routing, RSI, sidecar, external benchmark scoring/suite, unrelated historical task completion and full M1 acceptance.
- Consumed owned agreements: [M0-IF-001@r1](TASK.md#m0-if-001-at-r1), [M0-IF-002@r1](TASK.md#m0-if-002-at-r1), [M0-IF-003@r1](TASK.md#m0-if-003-at-r1). Generated contracts must identify the exact implementing revision.
- Permitted models: protected configured approved endpoint and retained Codex baseline/fallback interface per supplied architecture. No provider/model identifier is assumed. Effective identity and access are observed; absent approved access is a runtime BLOCKED prerequisite. A mock profile is labelled and isolated, with no live acceptance standing.
- Source choices: D5 fixed multi-pass and D6 container listen exceptions are explicit; current benchmark/architecture exact hashes override the conflicting old intake-hashing blacklist for protected evidence; direct standalone coding instruction overrides existing app reuse guidance. These decisions are recorded in TASK/register, not silently claimed literal PRD compliance.
- Empty authorized default docs directory is permitted; specified required unreadable material rejects. PDF extraction means local raw text only; complex OCR/vectorization/Office intake is excluded. Resources have stable captured identity/roles without automatic clone/download or full code/dataset reasoning ingestion.
- Only authorized conservative missing hardware default single_gpu is currently supplied. It neither proves a GPU exists nor requires a compiler-only GPU inference run. Future defaults/model lists/mandatory threshold inputs remain source-dependent rather than fabricated.
- Numeric operational bounds are frozen implementation safety configuration defined in plan before execution. Synthetic sample time/call values are illustrative. No production quality percentage, throughput/latency SLA or semantic reliability threshold is supplied; per-case expected behaviors derive from source obligations and labelled independent fixtures.
- System TASK: M0-001 owns its bounded integrated compiler journeys AC-014..024 and references its own block/boundary coverage. No unrelated full-M1 system spec is created.
- Diagnostic validation: all required template sections/AC/source rows are present; sources and process contradictions are explicit; material runtime-model/container prerequisites remain visible. No separate implementation checklist or human approval gate is introduced. Hooks file is absent at specification; no hook/branch/commit execution is authorized.

This is the AC authority. Implementation details belong in plan.md; progress and observed evidence links belong in tasks.md.
