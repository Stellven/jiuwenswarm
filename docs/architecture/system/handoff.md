---
type: design
status: draft
version: 2
owner: muk
sources: [../PROCESS.md, build-order.md, modules.md, verification.md, ../../../AGENTS.md]
provides: [system.handoff]
consumes: [system.module_map, system.build_order]
depends_on: [modules.md, build-order.md, verification.md, coder-requirements.md]
tags: [system, handoff, coding, m1]
---

# M1 coding handoff

This index defines no competing contracts. Read [coder requirements](coder-requirements.md), [build order](build-order.md), [module map](modules.md), then the owner pages below. Frozen PRD defines scope; the coding team converts architecture agreements into TASK/Spec Kit artifacts. Locations are proposed destinations. Internal algorithms remain coder choices.

## Complete module cards

Read [Docker modular-monolith deployment](deployment.md) before environment configuration: one application image/container, Linux execution on Linux Engine and macOS Docker Desktop, internal restricted processes, loopback workstation and benchmark endpoints. Installer/release work belongs at `deploy/` and `cc/bootstrap.py`; it owns image digest, launch policy, volumes, token provisioning and doctor, with actual runtime validation downstream. The benchmark API route table and schemas are the harness integration boundary.

Every card inherits [environment/config](environment.md), [confinement](../capsule/process-boundary.md), [storage/recovery](storage.md), [dispatch identity](records.md), [lifecycle](lifecycle.md) and [verification](verification.md). These answer security, environment, duplicates/timeouts/restart, write ownership and failure hooks. Rows supply specific placement/API/effects. The [fresh review](../reviews/2026-10-03-final-fresh-review.md) records connected design findings and dispositions. Pages retain draft status pending Muk's approval; schema success is not runtime validation. The [checkpoint manifest](../handoff-checkpoint-2026-10-03.json) pins this package.

| Module / location | API owner and responsibility | Writes and acceptance observation |
|---|---|---|
| config/startup/doctor `cc/config.py`, `bootstrap.py`, `doctor.py` | [environment](environment.md): effective configuration and readiness | config snapshot; invalid profile prevents launch |
| entry/session/UI `cc/adapters/entry.py`, `local_session.py`, `runview.py` | [workstation](workstation.md): run/status/inspect/abort/artifacts and terminal review | submission/review refs; token/path errors; views never release |
| launcher/halt `cc/launcher/` | [toolchain](../capsule/toolchain.md), [lifecycle](lifecycle.md): launch/resume/abort/advance | run/dispatch/release records; failed Gate save prevents next invocation |
| plan adapter `cc/adapters/swarmflow.py`, `plan_script.py` | [integration](integration.md), [nodes](nodes.md): generic script/`CcBackend` | journal is cache; spy on actual next dispatch |
| freeze `cc/freeze.py` | [toolchain](../capsule/toolchain.md): closure and typed bindings | atomic Binding batch; missing dependency refused |
| store/records/hash `cc/store.py`, `records.py`, `hashing.py` | [storage](storage.md), [records](records.md), [toolchain](../capsule/toolchain.md) | supervisor sole writer; corrupt/interrupted/conflict hooks |
| vocab/policy/kit `cc/vocab.py`, `policy/`, `kit.py` | [toolchain](../capsule/toolchain.md), [authoring](../capsule/authoring.md) | schema/policy/Candidate refs; no mutable released schema |
| admission/activation `cc/admission.py` | [admission](../capsule/admission.md), [library](../capsule/library.md) | Verdict/Standing/activation; Puppet cannot certify or runtime-pass |
| runner/broker/SDK `cc/runner/`, `cc_sdk/` | [runner](../capsule/runner.md): authenticated typed calls | capture/Artifact/Observation; output/timeout/cancel failures |
| model bridge `cc/model.py`, `cc/adapters/model_bridge.py` | [runner](../capsule/runner.md), [environment](environment.md) | lossless turns; fake delayed/auth-failed replies |
| checks/Gate `cc/checks/`, `cc/gate.py` | [gate host](../capsule/gate-host.md): deterministic checks, semantic assessment/fold | durable Verification; unknown/write fault blocks |
| eight work capabilities `capsules/research.<capability>/` | [pipeline](../m1/pipeline.md): Brief/Search/Screening/Hypothesis/POC/scientific execution/Evaluation/Report | canonical stage payloads; stage checks/evidence |
| shared `research.verifier` | [research Gates](../m1/research-gates.md): pinned stage criteria | assessment only; Gate host remains authority |
| mechanical helpers `cc/research/` | [pipeline](../m1/pipeline.md): extraction, IntentIR, ranking/arithmetic, resource/compiler/publication | artifacts via supervisor; pure fixture checks |
| three search capabilities `capsules/op.<search>/` | [operators](../m1/order.md), [integration](integration.md) | bounded hits/evidence; external unavailable/malformed results |
| measurement `cc/measurements/`, `cc/security/measurement_service.py` | [protocol](../m1/measurement-protocol.md): trusted arm/method execution | raw/sample refs; forged/wrong-arm evidence fails |
| generated-code service `cc/security/poc_service.py`, platform launcher | [process boundary](../capsule/process-boundary.md) | logs/security evidence; unsupported/escape denies execution |
| Data Foundation `cc/evidence.py`, `cc/data/` | [storage](storage.md), [seam](../seams.md#data-foundation) | capture/bundles/derived views; no invented capture |
| progress `cc/events.py` | [observability](observability.md) | optional events/spans; reconnect reads authoritative state |
| offline RSI `cc/rsi/` | [RSI engine](../capsule/rsi-engine.md): bounded attempts/Candidate | hash-chain; violation halt; no activation |
| private oracle `cc/security/oracle.py` | [oracle](../capsule/fixture-oracle.md) | private quota/referee records; no fixture export |
| planner/validator `cc/planning/`, `cc/adapters/leader.py` | [planner](planner.md): Leader proposal then deterministic validation | proposal/validation artifacts; invalid/save failure means zero dispatches |
| experimental adapters `cc/experiments/entry.py` | [track isolation](experiments.md) | experimental pins/deviations; forbidden production feature refused |
| external benchmark `cc/benchmark_api.py`, `cc/data/export.py` | [benchmark export](benchmark-export.md): headless run/export | immutable manifest; unavailable telemetry explicit |

## Downstream allocation

[Stories](../stories/README.md) give connected examples of these module cards in use: production payloads, scientific outcomes, persistence faults, auth, private RSI, planning and HTTP export. They are explanatory fixtures, not another API authority or executed acceptance evidence.

[Boundary-case index](boundary-cases.md) assigns invocation points and expected observations across all three tracks. [Final fresh review](../reviews/2026-10-03-final-fresh-review.md) records the corrected final findings. Runtime observations are still the coding team's responsibility.

Model-auth module card: `cc/model_auth.py` and `cc/adapters/codex_auth.py` implement [AuthProvider](model-auth.md), with the bridge as sole credential writer, dedicated named volume and device-login setup. Standalone cases cover login/cancel/expiry, profile contention, refresh persistence and secret exclusion. [Environment](environment.md) supplies ModelProvider call semantics so future endpoint/auth replacements remain confined to adapters.

[Build order](build-order.md) starts with shared durability and one producer/consumer seam, then completes production, required RSI and permitted experiments. Each coding task imports [generated schema hashes](../exports/manifest.json), owns module fixtures and depends on the owning shared-contract task. Saurav's future schema adapts at export, not scientific execution.

Use [spatial map](modules.md#process-topology) for code/process placement and [lifecycle](lifecycle.md), [planner](planner.md), [benchmark export](benchmark-export.md) and [RSI](../capsule/rsi-engine.md) for temporal order. [Coder requirements](coder-requirements.md) governs AI review, human decision summaries and pinned handoff releases.
