---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../PROCESS.md]
provides: [system.verification_surface]
consumes: [cc.gate_host, system.run_lifecycle, system.durable_storage]
depends_on: [../capsule/gate-host.md, lifecycle.md, storage.md, environment.md, workstation.md]
tags: [system, m1, acceptance]
---

# Component invocation and connected acceptance

This is an architecture specification for testable public interfaces and expected observations, not a report of implementation tests. Coding TASK/spec/plan/tasks own actual commands and results; no Spec Kit artifacts are authored here. Each module can be exercised through its public API with fake adjacent modules and immutable fixtures before an integrated run.

## Independent invocation surfaces

| Component | Invoke | Substitute / observe |
|---|---|---|
| Hash/vocabulary/author kit | functions and commands in [toolchain](../capsule/toolchain.md) | fixed bytes, type examples, admission report; no live model required |
| Store | put/get/commit_batch using a temporary local root | inject error before publication, after rename, during fsync, or corrupt bytes; observe committed manifests and typed errors |
| Runner | call through RunnerRequest with an admitted fixture capsule | fake model bridge, snapshot inputs, cancelled child, output/schema errors; observe capture/Artifact/Observation refs |
| Model bridge | turn/cancel/status through protected IPC | fake app-server with delayed/auth-failed/duplicate reply; observe exactly one turn and captured bytes |
| Gate | gate(obs_ref) with fixture Bindings and committed evidence | fake check runner and judge replies; observe durable Verification and absence/presence of authorization |
| Node control | authorize_advance and generic script with fake runner/Gate | spy on next dispatch; advance never occurs without a valid committed decision |
| POC service | execute_poc against a fixture bundle | offline wheelhouse, mock harness, timeouts, missing file, unauthorized path/network; observe raw logs and boundary evidence |
| Oracle | start/open session, evaluate, finalize through its private API | private seeded fixtures and planted wrong child; inspect aggregate response only, quota, inaccessible answers |
| Data Foundation | seal execution, assemble, export | repeated assembly, loss/corruption of required capture; verify byte-for-byte prompts/logs, ids/hashes, no invented counts |
| Entry/UI/config | load_config, doctor, public run API and native views | project-over-user overrides, unsupported platform, invalid token, reconnect; read the same durable state |
| Offline RSI | begin session, proposal attempt, submit and activate | planted forbidden mutation/regression, frozen referee, loop/final separation; observe append-only hash chain and no live activation |

Fixture owners supply check/rubric expected outcomes independently of builders (INV-10). Inject faults through supplied model, store, process, clock, collector and engine adapters; do not alter production product behavior to manufacture a pass. Inputs and expected outputs belong to owning TASK fixtures after handoff.

## Gate acceptance and recovery scenarios

All ten PRD 4.2.9 cases must have observable boundary evidence: valid pass; schema failure with Tier 2 NOT_RUN; swapped/stale artifact; unsupported claim; time-budget violation; prohibited code/tool; environment block; known limitation; scientifically negative but valid evaluation; and delayed Gate decision locking the next node. Assert actual next-node invocation count, not just a verdict string.

Additional persistence scenarios: decision computed PASS but save fails; decision durably saved but transport reply lost; engine journal passes while canonical Verification is absent/corrupt/wrong-attempt; freeze dies after one staged Binding; raw capture missing; repeated request id; pause/kill after an effect but before Observation. Expected outcomes are respectively halt/no release, recover existing decision, refuse cache authorization, no partial frozen run, environment/evidence block, same request/result or conflict, and explicit human-reviewed recovery. No autonomous repeated side effect is accepted.

## Research and security scenarios

For each payload: a valid example, required field removed, unknown core field, broken source/resource id, mismatched type/version and wrong-run reference. Screening includes equal scores, duplicate source ideas, all conflicts, missing rubric/registry and stable ordered output without selecting an internal sorting algorithm. Hypothesis/benchmark/evaluation cases distinguish acceptance target, claimed effect and falsification boundary; units, relative/absolute transform, zero denominator, missing measurements, plausibility anomaly, and scientific FAIL flow to Delivery. Domain classifications remain blocked by owner policy issues 10/41/44 rather than guessed by tests.

Negative security probes execute under the actual child identities: read home/.ssh/Codex auth/store/hidden fixtures/other run; escape via symlink or parent path; direct socket and forbidden tool; privilege escalation; malicious pip build; timeout with surviving grandchild. All are denied or execution is unavailable. Test the oracle comparator never sends expected output to candidate code, and loop/final hashes do not overlap. Probe supported platform/Python/wheel combinations; absent mechanism or unrun probe stays unsupported, not passed.

## Connected design and handoff

Measurement authority checks include a harness emitting plausible invented values, a forged/replayed measurement_ref, wrong arm/seed/method/config, missing workload capture and zero completed baseline invocations. Each must block despite valid sample JSON. Inject failure between measurement capture and commit; no complete sample is returned. System record checks include a killed dispatch without Observation, quota reservation before interruption, and repeated human-review/activation IDs. The native token-file probes include wrong owner/mode, symlink, expiry and stale service instance.

Architecture evidence for this pass: existing lint/schema/example/graph checks pass; the POC producer and Benchmark consumer were independently derived by fresh agents and the existing canary returned agree on poc_bundle with hypothesis_blueprint externally supplied. This is one checked seam, not a claim that every M1 seam has passed blind derivation. The fresh handoff review's seven verified findings are dispositioned in [open issues](../open-issues.md#review-dispositions-and-current-recheck-scope). New draft contracts still need area acceptance and owner/platform closure before complete coding handoff.

Architecture lint compiles schema tables, validates examples, checks links and module/datatype graph. Independently derive producer and consumer interfaces from their owner pages and run the existing seam canary. A fresh source reviewer checks PRD coverage and the seven coder questions; every verified finding is fixed or dispositioned to a named owner and affected modules. Changed contracts recheck the transitive consumer set.

Implementation integration follows startup/doctor, admission, freeze, intake-to-report, evidence reconstruction and explicit halt/resume. A full demonstration uses a small local baseline/dataset and reproducible model response fixtures, then the real authenticated model endpoint on a validated supported platform. A valid scientific FAIL is a successful governed research run. Record exact versions, fixtures, commands and observed results only after execution. This documentation session verifies architecture syntax/examples and reviewer findings; it cannot verify unbuilt runtime components.
