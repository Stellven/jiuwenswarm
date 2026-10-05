---
id: system.boundary-cases
type: design
status: proposed
version: 1
sources: [test-surfaces.md, ../../product/prd-m1-full-2026-10-02.txt]
provides: [system.boundary_case_index]
consumes: [system.verification_surface]
depends_on: [test-surfaces.md, modules.md, deployment.md, model-auth.md, experiments.md]
tags: [acceptance, cases]
level: detail
prd: [4.2.9, 4.6.4]
---

# Boundary-case coverage

PRD: 4.2.9, 4.6.4

> Answers: Which boundary cases are checked, at which invocation point, with which observation?

This index links cases to invocation points and expected observations. It adds no second contract authority. **Every row is specified, not executed against product code.** Builders create actual TASK [fixtures](test-surfaces.md#term-fixture)/commands and record observations. New faults found during implementation extend the owning contract and this index; a finite list is not proof that software has no undiscovered failures.

| Case [family](../contracts/principles.md#term-message-family) | Invocation and authoritative page | Required observation |
|---|---|---|
| Blank topic, unreadable workspace, unsupported/oversize/empty document | [launcher](../capsule/toolchain.md#m01-launcher), [intake](../types/intake.md) | reject invalid submission or record skipped reference reason without invented extraction |
| Repository/dataset/document classification, wrong locator, symlink escape, changed qualification | [intake](../types/intake.md), [HTTP entry](benchmark-export.md#behavior-docker-http-transport) | safe local inputs, canonical requalification and immutable [snapshot](../capsule/library.md#term-library-snapshot); mismatch refuses |
| Missing field, unknown field, wrong version/type, invalid reference/hash/scope | [types](../types/types.md), [contracts](../contracts/README.md), [store](storage.md) | refuse before consumer/effect; do not coerce into another version |
| Missing launcher [source_text](../types/source-text.md#term-source-text), intent output absent or failing its [Gate](../verification.md#term-gate) | [M01](../capsule/toolchain.md#m01-launcher), [intent compile](../capabilities/intent-compile.md) | required source projection bound; requirement step does not start without accepted intent (`PENDING_SOURCE` wiring: [decisions](../decisions.md#open)) |
| Contradictory requirement, ambiguous percent metric, source quote mismatch | [Brief](../capabilities/requirement-capsule.md), [Brief Gate](../capabilities/brief-gate.md) | attributed issues; ambiguity cannot become a scientific threshold by inference |
| Search unavailable/malformed service, code-index snapshot mismatch | [search](../capabilities/search-capsule.md), [operators](../capabilities/README.md) | bounded hits or typed halt, preserved source/evidence identity |
| Screening ties/duplicates/dependency conflict/all-ineligible | [Screening](../capabilities/screening.md), [ranking](../capabilities/op-rank-opportunities.md) | fixed rubric/ordering; preserved rejection reasons; no winner [halts](lifecycle.md#term-halt) |
| Blueprint baseline/target/falsification/middle-zone conflict | [Hypothesis](../capabilities/hypothesis.md), [protocol](../capabilities/measurement-protocol.md) | preregistered distinct predicates and usable resource/measurement pins |
| Missing POC file, undeclared dependency, online/sdist install attempt | [POC](../capabilities/poc.md), [process request](../capsule/process-boundary.md) | contract refusal or environment halt before scientific execution |
| Unsupported hardware/method, trusted sample unavailable, forged harness values | [measurement authority](../capabilities/measurement-protocol.md) | only attributable actual arm/workload samples; missing method [blocks](modules.md#term-block) selecting experiment |
| Wrong arm/repeat/seed/config, incomplete baseline, partial stdout, nonzero exit | [scientific execution](../capabilities/benchmark.md), [payload](../types/benchmark-payload.md) | retain partial evidence; no [released](lifecycle.md#term-release) complete benchmark |
| Zero denominator/nonfinite metric, equality/threshold boundary, post-hoc policy change | [Evaluation](../capabilities/evaluation.md), [protocol](../capabilities/measurement-protocol.md) | fixed arithmetic/classification or typed evidence failure |
| Scientific PASS/FAIL/INCONCLUSIVE/CONDITIONALLY_ACCEPTABLE | [verdict](../types/evaluation-verdict.md), [Write report](../capabilities/write-report.md) | valid science continues through real infrastructure Gate and truthful report |
| Unsupported claim, limitation, malicious tool/code, delayed judge | [Gate](../capsule/gate-host.md), [verification cases](test-surfaces.md) | PRD4.2.9 verdict/tier behavior, independent evidence and actual successor count |
| Nested [operator](../capabilities/README.md#term-operator) fails/mechanical Gate missing | [broker](../capsule/runner-broker.md#nested-calls-and-the-broker) | parent cannot consume an unverified nested output |
| Gate PASS but [Verification](../schemas/verification-record.md#term-verification) save fails; release save fails | [lifecycle](lifecycle.md), [records](records.md) | zero successor dispatch until exact durable authority exists |
| Lost reply after successful save; corrupted/wrong-attempt cache | [lifecycle](lifecycle.md), [nodes](nodes.md) | reuse exact committed result or refuse cached authorization; no repeated effects |
| Interrupted freeze/output/capture/manifest/publication write | [storage](storage.md), [records](records.md) | atomic committed state or recoverable interruption; no partial success |
| Duplicate request, conflicting bytes, busy instance | [lifecycle](lifecycle.md), [HTTP](benchmark-export.md) | same committed handle/status or conflict/busy before new work |
| Timeout/cancel/process or model-transport failure, surviving grandchild, process death | [process boundary](../capsule/process-boundary.md), [deployment](deployment.md) | owned namespace tree terminated/reaped, capture sealed, uncertain effects preserved |
| Benchmark HTTP caller disconnect after acceptance | [HTTP entry](benchmark-export.md#behavior-docker-http-transport) | accepted run continues; same request ID/status poll recovers handle without restart or implicit cancellation |
| Explicit resume versus new inputs/config/library | [recovery](lifecycle.md), [configuration](environment.md) | same pins and new attributable attempt; changed pins require new run |
| Alias changes between validation/freeze; revoked pinned version | [freeze](../capsule/toolchain.md), [library](../capsule/library.md) | exact snapshot version retained or denied; never substitute a current alias |
| Path/network/credential/store/fixture/other-run escape, helper override | [Docker](deployment.md), [confinement](../capsule/process-boundary.md) | deny under actual identities/profiles or mark execution unsupported |
| Linux/macOS Docker kernel/profile/wheel/GPU incompatibility | [deployment](deployment.md), [doctor](environment.md) | readiness fails closed; no unrun platform acceptance |
| Device login/cancel/expiry, corrupt/revoked auth, second profile writer, stale seed | [AuthProvider](model-auth.md) | safe local challenge/status, persistent exclusive cache, relogin requirement without secret export |
| Unsupported model, route judge timeout, unapproved fallback | [routing](../model-routing/README.md), [bridge](environment.md) | fixed or approved compatible route, no silent retry/failover after [turn](model-bridge.md#term-model-turn) begins |
| Run/admission/controller/oracle model scope, mixed identity, wrong capture namespace, failed private capture commit | [bridge scope](environment.md#model-call-scope-and-private-capture), [private custody](storage.md) | exact scope reservation and namespace authorization; no invented run/Candidate, private export or complete result before durable capture; cancellation uses a distinct management ID |
| Requested seed unsupported, unknown usage/cost | [config/bridge](environment.md), [export](benchmark-export.md) | requested/effective identity and explicit unavailable values, never fabricated zero |
| Puppet allowlist miss, forged integrity, invented suite/certification, auto-activation | [admission](../capsule/admission.md), [library](../capsule/library.md) | reject or honest exempt; no fabricated assurance/runtime pass/activation |
| Private trial/Candidate namespace confusion, visible-parent-suite failure | [RSI engine](../capsule/rsi-engine.md), [oracle](../capsule/fixture-oracle.md) | trials only before hidden evaluation; Candidate only after promotable final |
| One failure of three, known-bad/good [planted children](../capsule/fixture-oracle.md#term-planted-child), paired losses | [oracle score](../capsule/fixture-oracle.md#behavior-frozen-comparison-and-score) | all-three fixture rule, fixture denominator, fixed no-loss/Beta final decision |
| 31st session/91st lifetime query, interruption/reservation replay, pool copy | [oracle quota](../capsule/fixture-oracle.md) | durable budget exhaustion; no refund/reset or automatic repeat |
| Forged incumbent/lineage, partial/duplicate close, early/repeated final | [oracle API](../capsule/fixture-oracle.md) | exact closed schedule/evidence; one custodian final, terminal uncertainty |
| RSI-S01..S24 attack-suite failures, missing human clearance, changed profile bypass | [RSI verification](../capsule/rsi-engine.md), [private records](records.md) | attributable target-wide latch; verified human clearance and bounded explicit continuation |
| Planner cycle/missing input/wrong port/unreachable objective/budget/permission/Gate | [validator](planner.md) | structured INVALID evidence and zero dispatches |
| Planner (experiment track) timeout/duplicate, invalid or unsaved validation, live plan mutation | [planner](planner.md), [freeze](../capsule/toolchain.md) | no silent repair/reproposal or live rewiring |
| Experimental feature in production, missing access approval, native Code Mode custody failure | [tracks](experiments.md), [model auth](model-auth.md) | pre-dispatch refusal; experimental evidence cannot satisfy production acceptance |
| Ablation study absent/stale, disabled required producer, incompatible replacement | [study/validator](experiments.md), [service schema](../contracts/services-v1.schema.json) | refuse missing data path; no synthetic successor input |
| Disabled/partial Gate, failed experimental evidence/advance write, wrong-track replay | [experimental authority](experiments.md), [records](records.md) | truthful not_run/partial run bundle, no forged Verification/release, zero successor on failed publication |
| HTTP invalid token/body/path/profile, running export, corrupt artifact, unavailable evidence | [benchmark endpoints](benchmark-export.md) | scoped typed errors; no fixture/credential retrieval or fabricated bundle |
| UI dropped event/reconnect, stale token, wrong tmux session user, headless halt | [workstation](workstation.md), [observability](observability.md) | authoritative record view, denied stale session, no stdin wait or UI release authority |

Production [runs](lifecycle.md#term-run), offline [RSI](../rsi.md#term-rsi) and isolated experiments each have separate manifests; the production flow is in [flow](../flow.md), RSI in [rsi](../rsi.md). The benchmark harness's export schema (`PENDING_SOURCE`) is adapted at export; the external harness's internal scoring and tests stay outside this package.
