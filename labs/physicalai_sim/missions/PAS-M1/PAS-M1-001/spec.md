# Feature Specification: PAS-M1-001 - Base simulator
**TASK**: [TASK.md](TASK.md)
**Parent TASKS**: [../TASKS.md](../TASKS.md)
**Revision / date**: r1 / 2026-10-30
**Feature Branch**: `PhysicalAI-Sim` (the feature directory does not imply a branch)
**Input**: SIMLAB build input r0.4.3 (TASKS §1 hashes; r0.4.3 changed no phase 1 requirement, TASKS §6 C-04). PRD Main SL-1.D, SL-2.D/S, SL-3.D/S/B, SL-4.D/S/B, SL-5.D/S (MuJoCo part), SL-7.D/S (world-state part), SL-8.D/S, SL-9.D/B (tools part), SL-10.D/S (workstation, registry, doctor, resource records); PRD Context US-SL03, US-SL06, US-SL07; Architecture Main "Build order" phase 1, "Placement", "Required proof" X1.1 to X1.6, "AI4R connection" import rule; Architecture Context SIMLAB-IF-001, flows 4 and failure behavior, A-13; test plan "Rules", TB-01 to TB-09, F1, F5, phase 1 row, "Always", check groups, reports
**Status**: Specified (not a runtime result)

## Clarifications

### Session 2026-10-30
- Q: How should the TB-03 to TB-08 tolerances, which the test plan leaves as [confirm] values, be fixed? → A: The agent proposes each tolerance with a written reason in the frozen case before its first run, marked [confirm]; measured error is always reported; X1.2 is not claimed PASS until the owner confirms the values.

## User Scenarios & Testing

### User Story 1 - The real local setup fits (Priority: P1)
Before anything else is built on it, the owner learns whether AI4R, one real model-route request and a simulator process can run together on the laptop, and what they cost.

**Why this priority**: A-13 is the milestone's biggest risk; Architecture Main makes it the first check.

**Independent Test**: Start the AI4R app container on `127.0.0.1:5175`, send one real request through the lab's model route, and run a simulator process at the same time; read the resource and failure record.

**Acceptance Scenarios**:
1. Given a laptop with the AI4R baseline image and SIMLAB installed, when the feasibility run starts all three together, then a record shows each one started, the model request got a real answer, and peak RAM, CPU, VRAM and disk were measured.
2. Given the model route is unreachable or memory runs out, when the feasibility run executes, then the record keeps the real failure evidence and the result is FAIL or BLOCKED, never PASS. The owner decides any milestone change (A-13).

### User Story 2 - An agent builds, runs and inspects an experiment only through the tools (Priority: P1)
A coding agent with access only to SIMLAB's tools (MCP server, Python client or CLI) authors a scene, binds it into an experiment, validates, submits, follows status, and queries the data.

**Why this priority**: SL-9.D and X1.4; every later phase builds on this path, and the builder in phase 2 uses it.

**Independent Test**: Give an agent session only the SIMLAB MCP tools (no shell, files or repository) and a task to build and run a two-arm experiment; check that the run exists with data and that no other access was used.

**Acceptance Scenarios**:
1. Given an agent with only the tool interface, when it authors geometry, collision shapes, a model file, a procedure and a measurement and binds them, then an immutable manifest binds them to one experiment.
2. Given the same operation is performed through MCP, the Python client and the CLI, when results are compared, then they are the same.
3. Given a completed run, when the agent queries by run, arm, trial, time range and signal, then it gets the matching data.

### User Story 3 - A malformed experiment returns every finding at once (Priority: P1)
A requester submits an experiment with several defects and receives all of them together, each with a typed error, while clean experiments pass.

**Why this priority**: SL-4.D and X1.3.

**Independent Test**: Submit one experiment containing several independent planted defects, and a clean control; compare the findings with the planted set.

**Acceptance Scenarios**:
1. Given an experiment with N independent defects, when it is validated, then exactly those N findings come back in one response, each with a stable error code and location.
2. Given a clean control experiment, when it is validated and submitted, then it has zero findings and runs.
3. Given a defective experiment is submitted, then no run is created.

### User Story 4 - The simulator gives known answers (Priority: P1)
A researcher trusts SIMLAB's MuJoCo executor because the known-answer test benches TB-01 to TB-08, run through the tools, meet their frozen tolerances and report their measured errors.

**Why this priority**: X1.2 and SL-5.D (MuJoCo must pass its known-answer cases before research use).

**Independent Test**: Run the frozen F1 cases through the tool interface; an independent oracle compares the results with the analytic answers.

**Acceptance Scenarios**:
1. Given each case frozen with its model assumptions, initial conditions, measurement definition, horizon and tolerance, when it runs through the tools, then its measured error is reported and compared with the tolerance.
2. Given a deliberately wrong known-answer expectation (a control), when the check runs, then the affected measurements are marked invalid instead of being hidden.

### User Story 5 - Every trial, attempt and check is kept honestly (Priority: P1)
A researcher sees each result's checks, what actually ran versus what was missing, every attempt including failures, and whether the run is anchored.

**Why this priority**: SL-3.S, SL-4.S, SL-8.S and US-SL03. The runner never judges.

**Independent Test**: Run experiments that provoke each trial outcome (completed, numerical failure, physical divergence, limit reached, missing dependency, cancellation) and inspect the result records.

**Acceptance Scenarios**:
1. Given a trial that hits a numerical failure, then that attempt is INVALID with reason `numerical_failure` and the run continues with the remaining trials.
2. Given a trial that diverges physically, then it is COMPLETED, measured, and stopped at the declared limit.
3. Given an arm whose dependency is missing, then its attempts are BLOCKED with the reason and no substitute runs.
4. Given a run with no control arm and no known-answer check, then it is reported as unanchored and still runs.
5. Given any result, then it has no verdict field, and every execution has its own run identity.

### User Story 6 - Replay, save, restore and branch reproduce the run (Priority: P2)
A researcher replays a run, saves world state mid-run, restores it and branches a what-if, each reproduced on the same machine and build.

**Why this priority**: SL-7 (world-state part), X1.5, TB-09 and US-SL06. Whole-state checkpoints with controllers, memory and model calls come in phase 4.

**Independent Test**: Run an experiment; replay it; save at a declared point, restore and continue; compare each with the original by its declared comparison rule.

**Acceptance Scenarios**:
1. Given a completed run, when it is replayed on the same machine and build, then the replay is identical under its comparison rule and is recorded as a new run of kind `replay`.
2. Given a save at a declared point, when restored and continued, then the continuation equals the uninterrupted run under its comparison rule.
3. Given a saved state, when a branch is created with a changed intervention, then it runs as a new experiment referencing the saved state as its parent.

### User Story 7 - The operator can see what is supported and what each run cost (Priority: P2)
An operator runs the doctor, reads the capability registry, and gets resource records and check-group results for every run.

**Why this priority**: SL-10.D, X1.2 and the owner's compute tracking.

**Independent Test**: Run the doctor on a healthy and a degraded environment; run each check group including its negative controls; read the registry and resource records.

**Acceptance Scenarios**:
1. Given a healthy environment, then the doctor reports each readiness item as ready; given a degraded one (for example no model route or a writable source mount), it names the failing item with a typed failure.
2. Given a check group whose sources change during the run, then it exits with code 2; given one that exceeds its time limit, then it exits with code 124.
3. Given any run, then its record holds wall time, CPU time, peak RAM, GPU and peak VRAM when used, and disk written.

### User Story 8 - A fresh checkout reproduces a recorded result (Priority: P3)
Someone with a clean clone rebuilds the images from the lockfile and reproduces a recorded result without any hidden local files.

**Why this priority**: SL-7.S and X1.6. It depends on everything above existing.

**Independent Test**: Clone into an empty directory, rebuild, rerun a recorded experiment, and compare it with the recorded result.

**Acceptance Scenarios**:
1. Given a clean clone at the recorded commit, when the images are rebuilt from the lockfile and the experiment is rerun, then the result matches the recorded one under its comparison rule, and no file outside the clone and the declared inputs was read.

### Edge Cases
- An experiment references a parent run or checkpoint that does not exist: validation finding.
- An experiment declares a counted comparison without unit of inference, pairing, aggregation or required precision: validation finding.
- A protocol item has no origin: validation finding.
- A design that yields zero trials (for example zero replicates or episodes): validation finding.
- A save requested at a point the procedure does not declare: typed error; no checkpoint is written.
- Attempt to modify a submitted experiment or its manifest: typed error; nothing changes.
- An artifact changes after `bind`: a new manifest hash is required; the old experiment keeps its manifest.
- Component code at an extension point tries network access or reads credentials: denied by confinement and recorded.
- A record is corrupted on disk: affected attempt INVALID with `corrupted_record`.
- Cancel during a running trial: run CANCELLED, running attempt INTERRUPTED, completed trials kept.
- A required check fails: affected measurements invalid, not dropped or averaged; an unexpected outcome in an ordinary control arm is a result, not a failure.
- A replay on a different build or machine is not claimed identical (M1 claims identity only on the same machine and build).
- Model timeouts, bad answers, model budgets, crashes and restart are out of this TASK (PAS-M1-011 and PAS-M1-013).

## Requirements

### Functional Requirements
- **FR-001** (ARCH X1.1; ARCHC A-13; PRDC hardware): SIMLAB MUST provide a feasibility run that starts the AI4R app container on `127.0.0.1:5175`, sends one real request through the lab's model route, and runs a simulator process at the same time on the laptop, recording resource use and failures.
- **FR-002** (ARCHC IF-001): Experiments, results, manifests, statuses, measurements and typed errors MUST follow SIMLAB-IF-001@r1 as embedded in [TASK.md §4](TASK.md#simlab-if-001-at-r1).
- **FR-003** (PRD SL-1.D, SL-1.B): An experiment MUST record its objective, its objective kind (one of the seven kinds), sources, declared stand-ins and an optional parent run or checkpoint. Validation MUST never reject an experiment because of its kind.
- **FR-004** (PRD SL-2.D, SL-2.S; ARCH Placement): Authoring tools MUST create and change geometry and collision assets, model files, procedures and interventions, measurements and observations, and component code at declared extension points, and MUST end in an immutable manifest that binds them to one experiment. Agent-authored component code MUST run confined (no network, no credentials, declared limits).
- **FR-005** (PRD SL-4.D; ARCH X1.3): Validation before running MUST return all findings at once, each with a typed error; a defective experiment MUST NOT create a run.
- **FR-006** (PRD SL-3.D): The runner MUST execute any number of arms, factors, conditions, replicates and episodes, with paired trials, declared randomness, and measurements per trial, pair and set.
- **FR-007** (PRD SL-3.S; ARCHC failure behavior): The runner MUST keep every trial, attempt, failure and interruption; mark a trial invalid only for the six listed reasons; treat physical divergence as a completed, measured trial stopped at declared limits; end an attempt `LIMIT_REACHED` at a limit; continue the run after an invalid trial; and on cancel keep completed trials and mark the running attempt interrupted.
- **FR-008** (PRD SL-3.S, SL-3.B, SL-9.B): A submitted experiment MUST NOT change; every fresh execution MUST get a new run identity; the runner MUST NOT emit verdicts or interpret results, and MUST NOT rerun silently.
- **FR-009** (PRD SL-4.D, SL-4.S, SL-4.B; ARCHC evidence levels): Every result MUST carry its checks: sanity watchdogs, reruns across engine settings and assumed values ([confirm: 5] samples per arm), independent recomputation of standard measurements, and known-answer or control status. A run with neither control nor known-answer check MUST be reported unanchored. A failed required check MUST mark the affected measurements invalid, visibly. Each result MUST state its evidence level.
- **FR-010** (PRD SL-5.D; TP TB-01 to TB-08, F1): The MuJoCo executor, at a pinned version, MUST pass TB-01 to TB-08 run through the tools, each case frozen before it runs, each reporting its measured error.
- **FR-011** (PRD SL-7.S; ARCH X1.5; TP TB-09, F5): Replay MUST be identical on the same machine and build; save, restore and branch MUST reproduce the continuation; each MUST be checked with its own declared comparison rule.
- **FR-012** (PRD SL-7.D, world-state part): Save MUST capture the world state, random state, pending events and action history; restore MUST re-establish them; branch MUST create a new experiment whose parent is the saved state.
- **FR-013** (PRD SL-8.D): Results MUST return time series, events, contacts, measurements and checks, queryable by run, arm, trial, time range and signal.
- **FR-014** (PRD SL-8.S; ARCH Placement): Experiments MUST carry a feasibility record per dependency; arms whose dependency is missing MUST be BLOCKED with the reason. Every counted result MUST carry minimum provenance, kept in a declared durable data directory outside the repository.
- **FR-015** (PRD SL-9.D; ARCH X1.4): An MCP server, a Python client and a CLI MUST expose the same phase 1 operations and authoring tools with the same typed errors, sufficient for an agent with no other access to build, run and inspect an experiment.
- **FR-016** (PRD SL-10.D; ARCH Responsibilities, registry): A capability registry MUST list supported, excluded and missing capabilities, admitting an engine only by conformance results. A doctor command MUST report environment readiness with typed failures. Every run MUST record wall time, CPU time, peak RAM, GPU and peak VRAM when used, and disk written.
- **FR-017** (PRD SL-7.S; ARCH X1.6): A fresh checkout MUST rebuild the images from the lockfile and reproduce a recorded result with no hidden files.
- **FR-018** (ARCH X1.2; TP check groups): Check groups `core`, `executors`, `benchmark` and `all` MUST each run with one command, in an isolated environment with no network, a memory cap ([confirm: 4 GB]) and read-only sources; a source change during a run MUST exit 2 and a timeout MUST exit 124, each with a negative control; live or model-dependent tests MUST be opt-in and otherwise reported skipped, never passed with mocks.
- **FR-019** (ARCH Placement, "AI4R connection"; PRD SL-9.B; TP "Always"): The simulator process MUST hold no credentials; executors MUST have no network; SIMLAB MUST open no host port (the only host port is AI4R's 5175); nothing in `labs/physicalai_sim/` may import AI4R code, enforced by an import check.
- **FR-020** (TP Rules, F1, F5, case format): The F1 (TB-01 to TB-09) and F5 (replay) cases MUST be frozen as SIMLAB-Bench cases following the team's Harbor format, graded by an independent oracle, with three variants per family and three repeats where applicable, a hardware inventory before each run, failed runs kept, and per-family results with no aggregate score.
- **FR-021** (TP "Official external benchmarks", phase 1): The test benches MUST take their patterns and formulas from MuJoCo's engine tests, Drake's inclined-plane and friction tests, the seven analytic tests of arXiv 2603.14634 and ContactBench's criteria, and be rerun on every MuJoCo upgrade; a speed and cost record MUST be produced with MuJoCo's speed harness for the pinned build.
- **FR-022** (PRD SL-10.S; TP "Reports and evidence"; owner compute tracking): The phase 1 exit MUST produce a verification snapshot with failures kept beside passes, and a phase 1 completion report with every section the test plan lists, ending with a compute summary.

### Key Entities
Experiment, manifest, run, trial, attempt, measurement, check, checkpoint, trace, feasibility record, capability registry entry, resource record, typed error. Their fields and semantics are owned by SIMLAB-IF-001@r1 ([TASK.md §4](TASK.md#simlab-if-001-at-r1)); [data-model.md](data-model.md) describes how this TASK stores them.

## Success Criteria

### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | X1.1, A-13, PRDC hardware / FR-001 / US1 | One feasibility run starts the AI4R app container (listening on `127.0.0.1:5175`), completes one real model-route request with a non-empty answer, and runs a simulator process concurrently; the record holds peak RAM, CPU time, peak VRAM, disk written and every failure. A route or memory failure is recorded as FAIL or BLOCKED with its raw evidence; it is never PASS | BOUNDARY |
| AC-002 | IF-001 / FR-002 | Schemas for experiment, result, manifest, typed error and the status enums exist under the IF-001@r1 label; valid examples pass; each example missing a required field, carrying an unknown field or an out-of-enum status is rejected with the expected error code | BLOCK |
| AC-003 | SL-1.D, SL-1.B / FR-003 | Experiments of all seven objective kinds validate with zero kind-related findings; a missing objective, an invalid kind or a nonexistent parent each yields its typed finding; a follow-up with a valid parent run or checkpoint records it in the result | BLOCK, BOUNDARY |
| AC-004 | SL-2.D, SL-2.S / FR-004 / US2 | Through the tools: each artifact category (geometry and collision, model file, procedure and intervention, measurement and observation, component code at an extension point) can be created and changed; `bind` yields a manifest listing every artifact's SHA-256; identical content gives the identical manifest hash; changing any artifact after binding cannot alter the bound experiment; component code attempting network access or credential reads is denied and the denial recorded; component code exceeding its declared time, memory or process limits ends its attempt `LIMIT_REACHED` | BOUNDARY |
| AC-005 | SL-4.D, X1.3 / FR-005 / US3 | An experiment with N ≥ 5 independent planted defects returns exactly N findings in one `validate` response, each with its expected code and location (no missing, no extra); `submit` of it creates no run; the paired clean controls return zero findings and complete | BLOCK, BOUNDARY |
| AC-006 | SL-3.D / FR-006 | A fixture experiment with at least 3 arms, 2 factors, 2 conditions, 2 replicates and 2 episodes, with pairing and a declared seed policy, produces exactly the expected set of trials, with measurements at trial, pair and set scope; rerunning with the same seeds gives the same trial set | BLOCK, BOUNDARY |
| AC-007 | SL-3.S, ARCHC failure rows / FR-007 / US5 | Planted cases produce: `INVALID` with each of the six reasons (one case each) while the run continues; physical divergence `COMPLETED` and stopped at its declared limit; a horizon or wall limit `LIMIT_REACHED`; cancel mid-trial gives run `CANCELLED`, the running attempt `INTERRUPTED`, completed trials kept; cancel of a queued run gives `CANCELLED` with no attempts. Every attempt appears in the result | BLOCK, BOUNDARY |
| AC-008 | SL-3.S, SL-3.B, SL-9.B / FR-008 | Modifying a submitted experiment or its manifest returns a typed error and leaves bytes unchanged (hash compare); two submissions of one experiment give two distinct run IDs; the result schema has no verdict field and the runner writes none; the number of executions recorded equals the number of attempts in the result (no silent reruns) | BLOCK, BOUNDARY |
| AC-009 | SL-4.D, SL-4.S, SL-4.B, ARCHC evidence levels / FR-009 / US4, US5 | Each completed result carries watchdog, rerun ([confirm: 5] samples per arm), recomputation and anchoring checks. Watchdogs: a non-finite state makes the attempt `INVALID` (`numerical_failure`); exceeding a declared physical bound (for example penetration, energy growth or speed) is recorded by the watchdog and stops the trial at that limit. Reruns vary the declared engine settings and assumed values; each measurement's observed variation is reported, and the rerun check fails only when that variation exceeds a declared required precision. Each standard measurement is recomputed from the raw traces by separate code and compared within its declared tolerance (the `checks` entry's `tolerance`, IF-001 §5 A1); a run without control or known-answer check is `unanchored` and still runs; a planted failing required check marks exactly its dependent measurements `invalid` and they remain visible (not removed or averaged); an unexpected control-arm outcome is a result, not a failed check; a counted comparison missing unit of inference, pairing, aggregation or precision is a validation finding; each result states `evidence_level` (`simulation` when its required checks pass) | BLOCK, BOUNDARY |
| AC-010 | SL-5.D, TB-01 to TB-08, F1, Q-01, Q-02 / FR-010 / US4 | Each of TB-01 to TB-08, run through the tool interface on the pinned MuJoCo version, reports its measured error, which is within its frozen tolerance: TB-01 period error ≤ 0.5% [confirm] for small and large swing, TB-02 position error ≤ 0.1%, TB-03 to TB-08 within the tolerance frozen in each case before its first run (proposed with a written reason, marked [confirm]; see Clarifications). Negative controls fail: TB-06 with a frozen or over-damped simulation, TB-08 with gravity off. AC-010 is not PASS while any of its tolerances is unconfirmed by the owner | BOUNDARY |
| AC-011 | X1.5, TB-09, F5, SL-7.S / FR-011 / US6 | On the same machine (same host and CPU model) and the same build (same SIMLAB image digest, which pins the engine version and the lockfile): replay of a recorded run is identical under its rule (bitwise-equal recorded state trajectories and measurements); restore-and-continue equals the uninterrupted run under its rule; a branch reproduces the parent up to the save point and is a new run with the checkpoint as parent. Each rule is declared before the run; a perturbed control (changed seed) is detected as different | BOUNDARY |
| AC-012 | SL-7.D (world-state part) / FR-012 / US6 | A saved state contains world state, random state, pending events and action history; restoring it into a fresh process and continuing matches the uninterrupted run (AC-011 rule); a checkpoint missing any of these parts is rejected with a typed error | BLOCK, BOUNDARY |
| AC-013 | SL-8.D / FR-013 / US2 | For a completed run, `query` by each key (run, arm, trial, time range, signal) and their combinations returns exactly the matching records, and `fetch` returns time series, events, contacts, measurements and checks whose values equal those written during the run | BOUNDARY |
| AC-014 | SL-8.S, ARCH Placement / FR-014 / US5 | Every counted result has all minimum-provenance fields non-empty and stored under the declared data directory outside the repository; an arm with a `missing` dependency has every attempt `BLOCKED` with that dependency's reason and no substitute output | BLOCK, BOUNDARY |
| AC-015 | SL-9.D, X1.4 / FR-015 / US2 | The MCP server, Python client and CLI list the same operation set; one scripted scenario run through each gives equal results and errors; an agent session restricted to the SIMLAB MCP tools (no shell, file or repository access) builds, runs and inspects a two-arm experiment, and its tool log shows no other access | BOUNDARY |
| AC-016 | SL-10.D, owner compute tracking / FR-016 / US7 | The registry lists MuJoCo `admitted` only after its F1 cases pass, plus excluded entries with reasons (for example Isaac Sim on this laptop); the doctor reports every readiness item and, in at least three degraded set-ups, names the failing item with its typed failure; every run record and each `compute-log.csv` row has wall time, CPU time, peak RAM, GPU and peak VRAM when used, and disk written | BLOCK, BOUNDARY |
| AC-017 | X1.6, SL-7.S / FR-017 / US8 | From a clean clone at the recorded commit, the images rebuild from the lockfile and rerunning a recorded experiment matches the recorded result under its rule; the run reads no file outside the clone and its declared inputs | BOUNDARY |
| AC-018 | X1.2, TP check groups, Q-01 / FR-018 / US7 | Groups `core`, `executors`, `benchmark` and `all` each run with one command inside an isolated environment with no network, a [confirm: 4 GB] memory cap and read-only sources, writing the five evidence files; each group's negative controls give exit 2 (source change) and exit 124 (timeout); model-dependent tests are reported skipped unless opted in. X1.2 passes only when every phase 1 test bench passes to its frozen specification in these groups | BOUNDARY |
| AC-019 | ARCH Placement and "AI4R connection", SL-9.B, TP "Always" / FR-019 | The import check finds no AI4R import under `labs/physicalai_sim/` and fails on a planted one; a network attempt from inside an executor fails; the simulator process environment holds no credentials; a host listening-port audit during a run shows no SIMLAB host port (only AI4R's 5175 when it is running) | BLOCK, BOUNDARY |
| AC-020 | TP Rules, F1, F5, case format / FR-020 | `labs/physicalai_sim/benchmarks/` holds F1 cases (TB-01 to TB-09) and F5 replay cases, each with objective, inputs, grading and primary metric declared (B01), at least three variants per family, an independent stdlib oracle with tests on correct, defective and missing evidence, a frozen release with a SHA-256 manifest, and `smoke` and `campaign` profiles; a campaign run records a hardware inventory first (B17), three repeats where applicable, keeps failed runs (B08), and writes a dated report folder with per-family results and no aggregate score | BOUNDARY |
| AC-021 | TP "Official external benchmarks" phase 1 / FR-021 | Each TB case cites the adopted reference pattern or formula it uses; the cases rerun on a MuJoCo version change (the pinned version is an input to the case manifest); a speed and cost record from MuJoCo's speed harness (steps per second with active contact and control, wall time, CPU, peak RAM) exists for the pinned build on the laptop | BOUNDARY |
| AC-022 | SL-10.S, TP reports, owner compute tracking / FR-022 | `missions/PAS-M1/verification/YYYYMMDD/` holds the phase 1 snapshot with failures beside passes; `missions/PAS-M1/reports/PAS-M1_Phase1_Completion_Report.md` has every section the test plan lists (scope and exits; commit, images and hardware; results per exit linked to evidence; test bench errors; results per family; official benchmark results; deviations; retained failures and negative controls; blocked items; capability gaps; limitations; owner approval) and ends with a compute summary (totals, heaviest runs, peak memory against 6 GB WSL and 6 GB GPU) | Document check over runtime evidence |

All required behavior, failure cases and nonfunctional constraints above have AC coverage. Runtime verification is required for every behavior AC. AC-022 is a documentation check over runtime evidence and never replaces it.

## Scope and Assumptions
- Included / excluded scope: TASK.md §1. Model timeouts, bad answers, model budgets and fallbacks belong to PAS-M1-011; crashes, restart, concurrency and whole-state checkpoints with controllers, memory and model-call history to PAS-M1-013; pilot runs and preview to PAS-M1-002.
- Consumed TASK agreements: none. This TASK owns SIMLAB-IF-001@r1.
- Permitted models: no model is under test in this TASK. AC-001 sends one request through the lab's model route as configured in the pinned AI4R baseline; this TASK names no model.
- Assumptions and unresolved source inputs: [confirm] values from TASKS §6 Q-01 are used as declared; TB-03 to TB-08 tolerances (Q-02) are proposed in the frozen cases and confirmed by the owner before AC-010 can pass (Clarifications); A-13 is decided by AC-001's evidence.
- System tasks: PAS-M1-SYSTEM reruns this TASK's checks on the integrated candidate (SYSTEM/AC-003); it does not copy these ACs.

This is the AC authority. Implementation details belong in plan.md; progress and evidence links belong in tasks.md.
