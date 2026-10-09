# Feature Specification: M0-001 — Complete standalone Intention Compiler

**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [M0/TASKS.md](../TASKS.md)
**Revision / date**: r1 / 2026-10-08
**Feature Branch**: `ai4r_test_with_spec_kit_cut_detail` (existing; no branch action)
**Input**: Supplied PRD Main §4.7.1–5, relevant PRD Context §3.1–3.2/global compiler constraints; Architecture Main completion/foundations/proof and required assigned Context links; benchmark interface contract items 1–4/current versions; [exact source baseline](evidence/source-baseline.json).
**Status**: Specified; runtime verification NOT_RUN

## User Scenarios & Testing

### User Story 1 — Obtain a faithful released research contract (Priority: P1)

An authorized user submits an actionable scientific research purpose and local context, and receives a readable Research Brief preserving the requested work, scope, resources, targets and constraints without an invented solution or experiment.

**Independent Test**: Supply the labelled actionable and permissible-omission requests; inspect source-backed Intent, Brief, checking/review/decision records and exact release identity. A real configured-model request must separately reach release; teaching fixtures prove representations only.

**Acceptance Scenarios**:
1. Given a qualified actionable request, when the whole bounded compiler executes, then Intent and Brief are checked and independently reviewed, both subnode decisions and the final durable node release exist, and the bounded consumer receives the exact released Brief.
2. Given optional hardware/method/numeric threshold omission, when the compiler executes, then only authorized parameter defaults are visibly attributed; purpose, scientific solution, threshold and observed hardware are not invented.
3. Given explicit measurable targets and hard limits, when requirements compile, then their values, units/comparisons/scope and linked acceptance/evidence obligations survive into the Brief.

### User Story 2 — Inspect an attributable halt without further spending (Priority: P1)

The user receives a visible stable reason and retained candidate/evidence when meaning is unusable or an invocation, check, authority, budget or persistence boundary fails. Headless work terminates without waiting for a reply.

**Independent Test**: Exercise topic-only, contradiction, unsupported addition, malformed work/review, missing/duplicate findings, stale/hash-swapped refs, timeout/no output and storage failure. Assert dispatch counts, halt reasons, empty external accepted inventories and preservation of actual evidence.

**Acceptance Scenarios**:
1. Given topic-only or materially contradictory intent, when semantic review blocks it, then Requirements never dispatches.
2. Given malformed work output, when deterministic checking fails, then the verifier is not called; missing criteria or stale subjects never advance despite a claimed PASS.
3. Given missing model access or no output, when work cannot complete, then real failure receipts/observations explain the halt and no fabricated output ref is exported.
4. Given failed durable recording, when a producer and reviewer both pass, then no accepted output is published.

### User Story 3 — Control and reconcile one durable run through ordinary clients (Priority: P1)

Browser, API and headless clients share the same protected application decisions. They can verify readiness, submit/reconcile, inspect candidates versus releases, explicitly cancel and export readable evidence.

**Independent Test**: Use the actual authenticated HTTP service from a client; repeat/reconcile an identical request ID, attempt conflicting reuse, disconnect/reconnect, cancel between/within calls, restart unfinished work and compare status/downloads with durable records.

**Acceptance Scenarios**:
1. Given a supported target/version/profile, when a unique request is submitted and transport is lost, then reconciliation resolves its original run without duplicate model work.
2. Given browser closure, when the client reconnects, then server-owned work/history remains available; closure alone has not cancelled or replayed anything.
3. Given explicit cancellation or engine interruption, when status is inspected, then cancellation stops new dispatch and interruption pauses without replay while retaining effects and accepted history.
4. Given successful, failed or blocked work, when an authorized export is requested, then named substantive records, exact identities and explicit missing/unavailable evidence are returned without credentials or private state access.

### User Story 4 — Run the bundled component with truthful real prerequisites (Priority: P2)

An operator starts one application image and obtains same-origin local UI/API/runtime plus persistent inspection. Unavailable model/runtime/enforcement prerequisites are reported honestly and do not become fixture success.

**Independent Test**: Start/recreate the actual Linux image with configured volumes and approved model access; verify entrypoint/UI/API/readiness/auth/IPC/enforcement/persistence. Separately run labelled live model challenges and report false acceptances/refusals and limitations.

**Acceptance Scenarios**:
1. Given supported actual prerequisites, when the image starts without a separate frontend script, then loopback users access the bundled UI/service and inspect persisted runs after recreation.
2. Given unavailable Docker, model authentication, required confinement or telemetry, when readiness/verification executes, then the affected prerequisite/check is explicitly unavailable/BLOCKED and no required pass is claimed.

### Edge Cases

Empty/undecodable request; unreadable required directory/resource; empty authorized default directory; unsupported or oversized material; Unicode code-point/CRLF source spans; duplicate IDs or dangling requirement refs; false source/default authority; qualitative target without numeric comparison; conflicting mandatory constraints; unsupported schema/version; unauthorized account/workspace/target/audience/path; mutated pins, cyclic subnodes, pooled authority; missing/duplicate/inconsistent assessment findings; stale/swapped run/node/attempt/subject/context; permitted nonblocking limitation versus failed mandatory criterion; absent artifact; aggregate/per-call budget overrun; unavailable token/cost telemetry; storage fault before commit; concurrent same-ID submit; disconnect, cancellation and restart. Full scientific outcomes/experiment recovery are omitted because downstream stages are excluded.

## Requirements

### Functional Requirements

- **FR-001**: Qualify protected authorized local intake, preserving original bytes and separately identified extracted text/resources, exact hashes/roles/rejections and Unicode offset basis; no enrichment or host profiling. Sources: PRD §4.7.2; Context §3.1; Architecture Main intake.
- **FR-002**: Produce attributed meaning covering purpose/change/result, scope, constraints/preferences/targets and uncertainty without scientific solution selection. Source: PRD §4.7.2; intent-design.md.
- **FR-003**: Establish exact supported schemas, unique IDs, allowed refs, spans and invocation identities before semantic spend. Source: critical schemas; reference/compiler-verification.md.
- **FR-004**: Independently assess submitted Intent fidelity/coverage/coherence/usability; optional omissions are allowed, unknown purpose/material conflict/unsupported additions are blocking. Source: PRD §4.7.3; intent-design.md.
- **FR-005**: Use the fixed noninteractive bounded two-work/two-review graph; Requirements sees only committed accepted Intent and release is protected aggregation without another semantic call. Source: Architecture Main; immediate-plan.md.
- **FR-006**: Produce stable scientific_research Research Brief 2.0.0 obligations, supplied inputs, typed limits/targets, deliverables, acceptance/evidence and confirmation. Source: PRD §4.7.1/4/5; Context §3.2.5–7; intent-and-requirements.md.
- **FR-007**: Apply only protected conservative missing-parameter defaults, record each actual affected field and authority, preserve qualitative targets/optional omissions and never default purpose or experiment-specific protocol. Source: default-policy; intent-and-requirements.md.
- **FR-008**: Check and independently review Brief preservation, completeness, normalization, default authority and usability; blocking unresolveds cannot release. Source: compiler-verification.md.
- **FR-009**: Mechanically validate every verifier assessment's exact subject/context/criteria/evidence and verdict consistency; assessment cannot replace work, alter policy or control workflow. Source: checking.md/guard-design.md.
- **FR-010**: Freeze admitted declaration/implementation/dependency pins, node/subnode contracts/check profiles/configuration and effective intersection of authority/limits. Source: node-execution.md/capsules.md.
- **FR-011**: Release exact reviewed Brief only after complete internal/aggregate obligations and durable artifact/decision/accepted commit. Source: Main completion; checking.md.
- **FR-012**: Enforce finite observed call/time and supported mandatory resource limits; token/cost unavailable remains unavailable and token limits block only with trustworthy telemetry. Source: PRD §4.7.4; model-routing.md.
- **FR-013**: Halt without repair/replay/hidden endpoint substitution, retain real failures/candidates and return finite stable non-success without questions. Source: failure-and-human.md; benchmark contract.
- **FR-014**: Preserve lifecycle/immutable evidence and exact durable acceptance through storage failure, cancellation, restart and browser disconnection. Source: Main browser/container; placement.md.
- **FR-015**: Expose versioned authenticated readiness/submission/reconciliation/status/cancel/export through one ordinary-client application boundary, with all required shared fields. Source: benchmark items 1–4; automation.md/field-catalog.md.
- **FR-016**: Bundle UI/service/runtime in one local application image; protect credentials/control, persist configured state/evidence and prove required startup/IPC/enforcement prerequisites or report blockers. Source: Main browser/container; placement.md.
- **FR-017**: Verify real configured-model supported and labelled challenge cases; retain actual errors/false acceptance/refusal/provider limitations independently of fixtures. Source: Main Required proof; compiler-verification.md.

### Key Entities

Qualified Intake and exact Source/Resource; Intent IR; Research Brief; admitted Capability and node/subnode Contract; frozen Check Plan/Review Context; Deterministic Result/Assessment; Gate Decision and Accepted Output; Invocation Observation; durable Run and named Run Bundle; client Request/Readiness/Status/Cancellation/Error. [TASK interface agreements](TASK.md#4-embedded-cross-module-agreements) own shared semantics; subordinate data-model explains relationships.

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD §4.7.2; Context §3.1; FR-001 / US1,2 | Authorized nonempty intake preserves exact original/extracted refs, roles/hashes and Unicode offsets; every invalid required input visibly rejects; empty approved default directory is allowed | BLOCK, BOUNDARY |
| AC-002 | PRD §4.7.2; intent-design / FR-002 / US1 | Intent preserves purpose/change/result/scope/constraints/preferences/targets supported by original intake and local material; no solution/enrichment/host fact invented | BLOCK, SYSTEM |
| AC-003 | Exact Intent schema; compiler-verification / FR-003 / US1,2 | Every required structural/identity/span/local-ID/pin check executes; malformed, duplicate, out-of-bounds, swapped refs halt before review | BLOCK, BOUNDARY |
| AC-004 | PRD §4.7.3; intent usability / FR-004 / US1,2 | Labelled actionable/optional-omission case can advance; topic-only, material contradiction and unsupported confident addition cannot dispatch Requirements | BLOCK, SYSTEM |
| AC-005 | Architecture Main completion; benchmark node sequence / FR-005 / US1 | Successful sequence has exactly Intention work, Intent review, Requirements work, Requirements review, protected finalization; only accepted Intent reaches Requirements; no dialogue/retry/fifth semantic call | BOUNDARY, SYSTEM |
| AC-006 | PRD §4.7.1/4/5; Context §3.2.5–6 / FR-006,007 / US1 | Brief 2.0.0 includes all mandatory contract fields; fixed scientific lane; targets/typed constraints/user obligations survive; defaults use protected policy and existing affected fields; no invented percentage/purpose/protocol/hardware availability | BLOCK, BOUNDARY, SYSTEM |
| AC-007 | compiler-verification Brief obligations / FR-008 / US1,2 | Dangling/duplicate obligation/input refs, false default authority, lost hard constraints, blocked unresolveds or unsupported target/solution fail required structural/semantic checks | BLOCK, SYSTEM |
| AC-008 | guard/checking assessment contracts / FR-009 / US2 | Exact subject/context and every assigned criterion appear exactly once with reason/evidence; malformed/stale/missing/duplicate/inconsistent assessment never releases; no producer/verifier control injection | BLOCK, BOUNDARY |
| AC-009 | Node/subnode/capsule authority contracts / FR-010 / US1,2,4 | Actual pinned admitted supported implementation and independently pre-bound current real calibration/challenge profile bind concrete run/parent/attempt; no cycles/pooled permissions/unadmitted mutation/fixture-only runtime eligibility; required enforcement and admission evidence is demonstrated or BLOCKED | BLOCK, BOUNDARY, SYSTEM |
| AC-010 | Main protected release; benchmark current versions / FR-011 / US1 | Exact Brief, two work decisions/reviews and required observations aggregate to persisted node gate/accepted commit; bounded consumer rejects candidate, wrong-hash/parent/run or unsupported version and reads only released Brief | BOUNDARY, SYSTEM |
| AC-011 | PRD §4.7.4; model budgets / FR-012 / US1,2,4 | Positive frozen time/memory caps and finite call cap apply at subnode and parent; overrun halts before further dispatch; actual usage is recorded, unknown token/cost null with reasons; trustworthy token ceiling violation blocks | BLOCK, BOUNDARY, SYSTEM |
| AC-012 | Main failure proof; failure policy / FR-013 / US2 | Timeout/missing access/no-output/fault deterministically halts with genuine observation/failure receipt and explicit non-success; absent output inventories stay empty, no unnecessary review/no automatic retry/substitution | BLOCK, BOUNDARY, SYSTEM |
| AC-013 | protected acceptance persistence / FR-011,014 / US2 | Injected artifact/decision/transaction failure exposes non-success and no accepted output; durable commit identity exists only after successful atomic release; orphan files grant no authority | BLOCK, BOUNDARY |
| AC-014 | benchmark submit/reconcile; automation / FR-014,015 / US3 | Same actor/workspace/request ID+content reconciles to one run and one dispatch sequence; conflicting content rejects; client/browser disconnect neither cancels nor replays | BOUNDARY, SYSTEM |
| AC-015 | Main cancel / FR-014,015 / US3 | Authenticated explicit cancellation stops every subsequent dispatch, contains active work and preserves effects/history; repeated cancel is stable; no redundant question | BLOCK, BOUNDARY, SYSTEM |
| AC-016 | Main restart / FR-014 / US3 | Restart of interrupted run preserves accepted artifacts/decisions, marks unfinished attempts paused, performs zero automatic replay; read-only inspection remains available | BOUNDARY, SYSTEM |
| AC-017 | benchmark readiness/config / FR-015 / US3,4 | Readiness declares correct app/build/instance/interface/schema/profile/operations plus separate auth/storage/model/required-enforcement states; wrong target/version/profile/unavailable prerequisite blocks submission | BLOCK, BOUNDARY |
| AC-018 | benchmark evidence/status/cancel; inspection / FR-015 / US3 | Actual authenticated UI/API/CLI expose identical stage/status/candidate/released refs/verdict/reasons; success/failure/blocked exports include all required named sources/contracts/pins/config/checks/assessments/gates/observations/hashes/limits/usage and explicit missing/redacted items; denied scope/path/credentials reject | BOUNDARY, SYSTEM |
| AC-019 | Main browser/image; placement / FR-016 / US4 | Actual Linux application image entrypoint starts bundled same-origin UI/API/runtime without external UI helper, publishes loopback 5173, protects auth/IPC/credentials/control and persists inspection after recreation; required unavailable runtime is BLOCKED | SYSTEM |
| AC-020 | Main real proof; benchmark client successful path / FR-017 / US1,4 | At least one actionable actual configured-model request reaches released Brief through ordinary client with inspectable raw evidence; labelled positive/negative challenges report all actual verdicts, false acceptance/refusal, repeats/sample counts and provider limitations. Missing protected admission-rate/sample threshold remains PENDING_SOURCE and prohibits a broad measured-quality/admission claim | SYSTEM |

All required checks must actually execute on an identified candidate to pass an AC. Fixture results alone never establish AC-019/020 or real enforcement portions of AC-009/011. No unspecified quality percentage or M1 release claim is added.

## Scope and Assumptions

- Included/excluded scope follows [TASK](TASK.md) and [source allocation](../TASKS.md); this is compiler component completion, not full Stage 2 or M1.
- Agreements: M0-IF-001/002/003@r1, canonical [TASK §4](TASK.md#4-embedded-cross-module-agreements).
- Permitted model route: fixed approved native Codex baseline from supplied PRD Context §4.3/5.6; actual configured model identity is an operator fact captured per run. An optional explicitly approved configured endpoint must be isolated/pinned and must not silently substitute for the baseline.
- Operator assumptions: initial protected configuration may use 360 seconds node time, 80 seconds per call, 2048 MB memory and 4 maximum calls. These are implementation profile choices, not fabricated PRD thresholds or teaching fixture proof. Source size/extension bounds are protected configurable qualification settings. All effective values/pins are retained.
- Unresolved inputs: M0-U03 quality threshold/sample protocol, M0-U04 actual model/enforcement/Docker prerequisites, and M0-U06 authoritative coding token/cost availability. No user questions; record impact and continue independent work.
- Architecture's D5/D6 source exceptions are explicit; supplied current PRD Main already allows multi-call sequence. User source-only standalone boundary overrides native-code reuse guidance.
- System TASK is this TASK; AC-020 owns complete compiler journey and references bounded ACs rather than duplicating their requirements.

This is the AC authority. Design/procedures belong in plan.md; progress/evidence in tasks.md.
