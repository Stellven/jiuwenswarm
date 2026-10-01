# Implementation Plan: M1-002 - Local configuration, identity and execution boundaries

**TASK**: [TASK](../../docs/tasks/M1/M1-002/TASK.md) | **Spec**: [r1](spec.md)
**Revision / date**: r1 / 2026-10-01 | **Branch**: implementation NOT_STARTED
**Input sources**: PRD r1 §5.4, §5.6; Architecture PENDING_SOURCE.

## Summary

Local single-user settings, source-defined configuration precedence, static endpoint aliases, local-session authentication, restricted execution requirements and budget configuration. The blocks below group observable responsibilities for planning; they do not prescribe classes, processes, services or module boundaries. Architecture must refine and bind them before dependent implementation.

## Technical Context

- Runtime/platform: source-defined local JiuwenSwarm/OpenJiuwen environment; exact supported versions and implementation paths PENDING_DESIGN.
- Source-mandated technologies: retain the relevant PRD configuration, native surface, local security and packaging requirements. They are not claims that upstream facilities are already verified.
- Model/provider: configured Codex CLI baseline in Phase 1; availability/authentication and actual model metadata must be recorded during execution.
- Storage: source-required local artifacts/evidence; exact realization belongs to provider agreements and Architecture.
- Environment/commands: PENDING_DESIGN; bind actual executable entry points and working directories before running checks. PRD example commands are not confirmed commands on this checkout.
- Quality/resources: reference spec ACs and declared experiment/configuration limits; no new release thresholds.

## Constitution Check

One TASK and one feature directory; owning spec ACs, embedded canonical agreements, one work/evidence matrix. Unresolved inputs affect only dependent work. All runtime checks are NOT_RUN and no commits, installs or product runs are part of document preparation.

## Project Structure

Current documents: `specs/M1-002-local-runtime-config/{spec.md,plan.md,tasks.md}` and `docs/tasks/M1/M1-002/TASK.md`. Future `evidence/` stores actual runs. Application, test and configuration paths: **PENDING_DESIGN**; inspect existing code and applicable subtree instructions before binding them.

## Blocks and Dependencies

| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Configuration / AC-001, AC-004, AC-005, AC-006 | Project/global configuration, local OS identity, authenticated session requests, declared execution permissions and configured capsule limits. -> Effective local configuration, authenticated local access and an execution boundary satisfying PRD permissions; schema, API, process and enforcement design PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |
| B02 | Security / AC-002, AC-003 | Project/global configuration, local OS identity, authenticated session requests, declared execution permissions and configured capsule limits. -> Effective local configuration, authenticated local access and an execution boundary satisfying PRD permissions; schema, API, process and enforcement design PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |
| B03 | Budgets / AC-007 | Project/global configuration, local OS identity, authenticated session requests, declared execution permissions and configured capsule limits. -> Effective local configuration, authenticated local access and an execution boundary satisfying PRD permissions; schema, API, process and enforcement design PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |
| B04 | Scope / AC-008 | Project/global configuration, local OS identity, authenticated session requests, declared execution permissions and configured capsule limits. -> Effective local configuration, authenticated local access and an execution boundary satisfying PRD permissions; schema, API, process and enforcement design PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |

Order: register missing architecture/policy inputs -> resolve relevant definition-time agreements -> implement/check independent behavior -> wire real participating blocks -> boundary checks -> system contribution. Shared runtime roles may have bidirectional evidence/decision flow; this is not a circular demand for whole TASK completion.

## Interfaces and Technical Decisions

- Canonical owned/consumed agreements: [TASK §4](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements); all current r0 agreements are semantic drafts.
- Source requirements are retained; technical decisions about storage, APIs, isolation, reload, lifecycle/cancellation and error representations are PENDING_DESIGN.
- No duplicate schema or invented provider identifier is supplied. Complete agreements and update their revisions when Architecture arrives.
- Fixture creation, exact procedure binding and test data versions are verification design work, not missing PRD features.

## Verification Design

| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BLOCK | B01 / AC-001 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Local real behavior; bounded stubs may isolate dependencies but not prove integration. | AC-001 in spec.md; retain the independently specified expectation. | Initialize a temporary local profile and supply a research prompt with domain constraints; inspect stored settings and intake context, and confirm no account-creation dependency. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V02 | BLOCK | B02 / AC-002 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-002 in spec.md; retain the independently specified expectation. | With a real local service, send authenticated and missing/invalid-token requests and attempt access from a non-loopback test client; retain binding, access-decision and permission evidence. Execute hostile cases only in an isolated test workspace. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V03 | BLOCK | B02 / AC-003 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-003 in spec.md; retain the independently specified expectation. | Prepare harmless protected sentinel files and controlled network targets in a disposable environment; run permitted and forbidden actions with the actual restricted identity, inspect IPC listeners and inject a degraded fixture permission. Retain denied/allowed observations and startup decision. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V04 | BLOCK | B01 / AC-004 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Local real behavior; bounded stubs may isolate dependencies but not prove integration. | AC-004 in spec.md; retain the independently specified expectation. | Use disposable run data to inspect and copy local files, then delete only the disposable data; verify product access reflects the deletion and no cloud sync is required. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V05 | BLOCK | B01 / AC-005 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-005 in spec.md; retain the independently specified expectation. | Load a configured Codex baseline and Searcher/Builder/Verifier aliases; inspect effective routing inputs and configuration reload behavior against the architecture-agreed interpretation. Redact credentials in retained evidence. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V06 | BLOCK | B01 / AC-006 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-006 in spec.md; retain the independently specified expectation. | Set conflicting global/project values and observe the effective value used by real intake/runner consumers. Use explicitly supplied test settings, not product defaults invented by the test. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V07 | BLOCK | B03 / AC-007 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-007 in spec.md; retain the independently specified expectation. | Supply an explicit finite test time/call limit, exercise below-bound and over-bound cases through the runner, and inspect the resulting stop event and recorded limit. Actual release configuration values remain separately registered. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V08 | BLOCK | B04 / AC-008 / M1-IF-002@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Local real behavior; bounded stubs may isolate dependencies but not prove integration. | AC-008 in spec.md; retain the independently specified expectation. | Inspect effective configuration, startup dependencies and exposed services of the candidate; confirm excluded controls are not prerequisites or active Phase 1 features. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V90 | BOUNDARY | M1-IF-002@r0 / AC-002, AC-003, AC-005, AC-006, AC-007 | Real providers and consumers for the resolved agreement; serialized inputs and negative cases, versioned before execution. | Corresponding source behavior crosses the real boundary unchanged; failed/unauthorized inputs cannot be shown as success. | Exercise provider/consumer paths referenced in the per-AC procedures after architecture binding; inspect returned behavior, error propagation, repeated-call effects as defined in the completed agreement, and evidence identity. Commands PENDING_DESIGN. | Working relevant blocks, completed agreement revision and real connection traces. |

The procedures above are preparation, not executed evidence. Each actual run records candidate identity (including dirty execution inputs), source/spec/plan/IF versions, environment, fixtures, commands, expected/observed outcomes and raw paths. Missing services/criteria or skipped assertions cannot pass. LLM-dependent checks record prompts, model metadata, dataset/split, repetitions and scoring procedure; choose repetitions before evaluation without inventing a source-mandated reliability score.

## System Candidate and Journeys

Provide relevant component/IF/configuration identity and valid feature evidence to [M1-SYSTEM](../M1-SYSTEM-governed-research/plan.md). Boundary wiring may precede final system acceptance; no completed system TASK is required to start independent feature preparation.

## Unresolved Decisions and Impact

- ARCH-002: Architecture must define effective configuration schema, reload semantics, platform mapping, privilege boundaries and IPC/authentication mechanisms. Do not claim that a venv or privilege drop alone proves filesystem/network confinement.
- POLICY-002: Budget values and any unspecified defaults come from registered product/configuration inputs; no universal numeric thresholds are invented.
- IF-002: Fixture-isolation startup behavior must be connected with M1-018 provisioning and M1-017 startup; definition-time coordination is required before dependent checks, not completion of the entire RSI loop.
- Populate the real code/test paths, commands, fixture versions and required environment before affected implementation/check execution. Update TASK changes and parent source allocation if any product behavior changes; invalidate affected evidence instead of overwriting history.

