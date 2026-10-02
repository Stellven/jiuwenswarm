# Implementation Plan: M1-019 - Isolated Phase 2 experiment registration and integration

**TASK**: [TASK](../../docs/tasks/M1/M1-019/TASK.md) | **Spec**: [r1](spec.md)
**Revision / date**: r1 / 2026-10-01 | **Branch**: implementation NOT_STARTED
**Input sources**: PRD r1 §1.3, §3.2.7, §4.3.1, §4.3.2, §4.7, §4.8, §4.9.1, §4.9.2, §6.12; Architecture PENDING_SOURCE.

## Summary

Separately scoped dynamic intention compilation, Leader/Cluster planning, dynamic discovery, mocked heterogeneous routing and OpenJiuwen Code Mode experiments only where explicitly designated by the PRD. The blocks below group observable responsibilities for planning; they do not prescribe classes, processes, services or module boundaries. Architecture must refine and bind them before dependent implementation.

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

Current documents: `specs/M1-019-experimental-tracks/{spec.md,plan.md,tasks.md}` and `docs/tasks/M1/M1-019/TASK.md`. Future `evidence/` stores actual runs. Application, test and configuration paths: **PENDING_DESIGN**; inspect existing code and applicable subtree instructions before binding them.

## Blocks and Dependencies

| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Isolation / AC-001, AC-005 | An operational comparable Phase 1 baseline, source-designated experimental feature descriptions and later registered experiment-specific architecture/product inputs. -> Isolated experimental execution and attributable comparison evidence; no automatic production promotion. Experimental payload/API design is PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |
| B02 | Compiler track / AC-002 | An operational comparable Phase 1 baseline, source-designated experimental feature descriptions and later registered experiment-specific architecture/product inputs. -> Isolated experimental execution and attributable comparison evidence; no automatic production promotion. Experimental payload/API design is PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |
| B03 | Routing track / AC-003 | An operational comparable Phase 1 baseline, source-designated experimental feature descriptions and later registered experiment-specific architecture/product inputs. -> Isolated experimental execution and attributable comparison evidence; no automatic production promotion. Experimental payload/API design is PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |
| B04 | Other tracks / AC-004 | An operational comparable Phase 1 baseline, source-designated experimental feature descriptions and later registered experiment-specific architecture/product inputs. -> Isolated experimental execution and attributable comparison evidence; no automatic production promotion. Experimental payload/API design is PENDING_DESIGN. Source invariants apply. | Relevant agreements in TASK §3; exact architecture edges PENDING_DESIGN. | PENDING_DESIGN |

Order: register missing architecture/policy inputs -> resolve relevant definition-time agreements -> implement/check independent behavior -> wire real participating blocks -> boundary checks -> system contribution. Shared runtime roles may have bidirectional evidence/decision flow; this is not a circular demand for whole TASK completion.

## Interfaces and Technical Decisions

- Canonical owned/consumed agreements: [TASK §4](../../docs/tasks/M1/M1-019/TASK.md#4-embedded-cross-module-agreements); all current r0 agreements are semantic drafts.
- Source requirements are retained; technical decisions about storage, APIs, isolation, reload, lifecycle/cancellation and error representations are PENDING_DESIGN.
- No duplicate schema or invented provider identifier is supplied. Complete agreements and update their revisions when Architecture arrives.
- Fixture creation, exact procedure binding and test data versions are verification design work, not missing PRD features.

## Verification Design

| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BOUNDARY | B01 / AC-001 / M1-IF-019@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-001 in spec.md; retain the independently specified expectation. | Run the baseline without experimental components and compare its static routing/DAG/gate policies with an experiment-enabled isolated candidate; disabling a track must not remove Phase 1 functionality. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V02 | BOUNDARY | B02 / AC-002 / M1-IF-019@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-002 in spec.md; retain the independently specified expectation. | Prepare research/code/spec requests, irrelevant repository/history context and an ambiguous request. Verify the source-defined experimental classification, relevant context filtering, interactive clarification and Leader-consumable contract while the static fallback remains unchanged. Exact realization and additional unstated quality thresholds remain pending. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V03 | BLOCK | B03 / AC-003 / M1-IF-019@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Local-real registry/router with source-authorized mocked candidate APIs; record the judge dependency mode. Candidate API stubs are valid for this routing experiment, not live candidate availability/quality. | AC-003 in spec.md; retain the independently specified expectation. | Supply mock metadata covering the source-defined candidate categories; run the actual routing logic against a DAG-provided capsule and verify compatibility filtering, lightweight LLM-based selection and unchanged Phase 1 routing. Record the selection judge service/configuration separately. Mock candidate APIs establish routing behavior only, never actual candidate availability or quality. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V04 | BOUNDARY | B04 / AC-004 / M1-IF-019@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-004 in spec.md; retain the independently specified expectation. | With a valid experimental Research Brief, inspect bounded Leader decomposition and generated dependencies; inject a disconnected node/missing dependency/capability mismatch and observe pre-dispatch rejection/replanning. On an isolated Code Mode branch, inspect provisioned workspace/dependency discovery and AST-aware diff/multi-file changes. Dynamic discovery acceptance beyond its named scope remains PENDING_SOURCE. Record the comparable baseline and all actual changes. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V05 | BOUNDARY | B01 / AC-005 / M1-IF-019@r0 | Controlled source-relevant fixtures; versions PENDING_DESIGN. Actual connected local services; external-real when needed. Stubs alone cannot pass. | AC-005 in spec.md; retain the independently specified expectation. | Compare source versions and enabled baseline features before/after an isolated experiment; verify no automatic promotion occurs and any requested promotion has traceable revised source coverage. Actual command and working directory PENDING_DESIGN. | Bound implementation + resolved inputs; candidate/source/IF/config identities, raw inputs/outputs, logs and retained run record. |
| V90 | BOUNDARY | M1-IF-019@r0 / AC-001, AC-002, AC-003, AC-004, AC-005 | Real providers and consumers for the resolved agreement; serialized inputs and negative cases, versioned before execution. | Corresponding source behavior crosses the real boundary unchanged; failed/unauthorized inputs cannot be shown as success. | Exercise provider/consumer paths referenced in the per-AC procedures after architecture binding; inspect returned behavior, error propagation, repeated-call effects as defined in the completed agreement, and evidence identity. Commands PENDING_DESIGN. | Working relevant blocks, completed agreement revision and real connection traces. |

The procedures above are preparation, not executed evidence. Each actual run records candidate identity (including dirty execution inputs), source/spec/plan/IF versions, environment, fixtures, commands, expected/observed outcomes and raw paths. Missing services/criteria or skipped assertions cannot pass. LLM-dependent checks record prompts, model metadata, dataset/split, repetitions and scoring procedure; choose repetitions before evaluation without inventing a source-mandated reliability score.

## System Candidate and Journeys

Provide relevant component/IF/configuration identity and valid feature evidence to [M1-SYSTEM](../M1-SYSTEM-governed-research/plan.md). Boundary wiring may precede final system acceptance; no completed system TASK is required to start independent feature preparation.

## Unresolved Decisions and Impact

- SOURCE-019: Further imported compiler behavior beyond the supplied source, additional Code Mode evaluation criteria, candidate model identifiers and experiment-specific quality thresholds require the relevant future inputs; do not infer them from old week3 model studies.
- ARCH-019: Experiment branch/checkouts, technical isolation and interfaces await Architecture; independent registration can proceed now.
- SCOPE-019: This is a preliminary non-release-blocking coordination TASK. Split into separate bounded experiment TASKs when their source detail arrives, maintaining source/AC ownership and retiring no IDs silently.
- Populate the real code/test paths, commands, fixture versions and required environment before affected implementation/check execution. Update TASK changes and parent source allocation if any product behavior changes; invalidate affected evidence instead of overwriting history.

