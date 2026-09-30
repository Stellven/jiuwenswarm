# AI4Research Complete Development Documentation v2

Complete English edition, including an English entry guide. Updated 2026-09-30.

TASKS -> TASK -> one Spec Kit per TASK.

This handbook contains every process guide, template, example, repository instruction and the future-M1 skeleton, plus the documentation-check record. Source files remain authoritative; this is a generated reading edition. Identifiers, commands and sample statuses retain their original meaning. It does not claim M1 runtime readiness.

[English entry](README.en.md) | [Chinese edition](AI4Research_Documentation_v2.zh-CN.md)

## Contents
1. [AI4Research Code SOP v2](#document-1)
2. [Verification: blocks, boundaries, system](#document-2)
3. [AI4Research development documentation v2](#document-3)
4. [TASKS: [PROGRAM-ID]](#document-4)
5. [TASK: [TASK-ID] - [Title]](#document-5)
6. [Verification run: [RUN-ID]](#document-6)
7. [Feature Specification: [TASK-ID - FEATURE NAME]](#document-7)
8. [Implementation Plan: [TASK-ID - FEATURE]](#document-8)
9. [Tasks: [TASK-ID - FEATURE]](#document-9)
10. [Spec Kit workflow for TASKS / TASK](#document-10)
11. [Git and integration](#document-11)
12. [v2 preparation and migration](#document-12)
13. [Repository AGENTS template for SOP v2](#document-13)
14. [Module/subtree AGENTS template](#document-14)
15. [AI4Research Repository Instructions](#document-15)
16. [AI4Research Constitution](#document-16)
17. [TASKS: M1](#document-17)
18. [Worked example: one small program, two TASKs](#document-18)
19. [TASKS: DEMO](#document-19)
20. [TASK: DEMO-001 - Normalize executor labels](#document-20)
21. [TASK: DEMO-SYSTEM - Verify the complete label journey](#document-21)
22. [Feature Specification: DEMO-001 - Label normalization](#document-22)
23. [Implementation Plan: DEMO-001](#document-23)
24. [Tasks: DEMO-001](#document-24)
25. [Feature Specification: DEMO-SYSTEM](#document-25)
26. [Implementation Plan: DEMO-SYSTEM](#document-26)
27. [Tasks: DEMO-SYSTEM](#document-27)
28. [Complete documentation catalog - SOP v2](#document-28)
29. [Documentation verification record](#document-29)

---

<a id="document-1"></a>

## 1. AI4Research Code SOP v2

Source: [docs/code/Code_SOP.md](Code_SOP.md)

<a id="document-1-heading-0"></a>

### AI4Research Code SOP v2
Revision: 2026-09-29. Prepare the complete M1 workflow while its PRD and architecture are still being written.

<a id="document-1-heading-1"></a>

#### 1. Hierarchy
**TASKS -> TASK -> one Spec Kit feature directory per TASK.**

- TASKS is the program register: source baselines, requirement allocation, task graph, interface index and system verification.
- TASK is the task's identity and entry point: executor, scope, exact native artifact paths, dependencies and embedded cross-module agreements.
- Spec Kit is the working core: spec.md defines acceptance; plan.md defines technical design and verification procedures; tasks.md holds ordered work, progress and the acceptance-to-evidence matrix.
- Evidence records actual verification results inside that feature directory. It is not another task list.

Uppercase TASKS.md is the program register. Lowercase tasks.md is one task's native work list. Install Spec Kit once per checkout; each TASK gets its own feature directory, not a separate tool installation.

A TASK is the logical task unit; TASK.md is its entry file. The task's functional specification (spec.md), implementation plan (plan.md), work list (tasks.md) and evidence belong to that TASK, but are separate files in its registered Spec Kit directory. TASK.md links to them; their full contents are not embedded in TASK.md.

There is no separate coding-authorization card, implementation checklist, test-report card, review card, handoff card, change-request card, or Manual design/plan track. Record the user's requested scope directly in TASK. This workflow introduces no reviewer-assignment or approval stage. Existing platform permissions and explicit user instructions still apply to actual external actions.

<a id="document-1-heading-2"></a>

#### 2. Single authorities
| Information | Authority |
| --- | --- |
| Product intent and complete M1 scope | Registered master PRD |
| System structure and architecture nodes | Registered master architecture |
| Source baselines, allocation, task dependency graph | TASKS.md |
| Task identity, executor, scope and artifact paths | TASK.md |
| Cross-module agreement | Owning TASK's interface section, with IF ID and revision |
| Task requirements, ACs and measurable thresholds | Native spec.md |
| Technical design, block boundaries and verification procedures | Native plan.md |
| Work progress and AC -> block -> check -> evidence matrix | Native tasks.md |
| Observed execution results | Feature evidence/RUN-ID.md and raw artifacts |

The PRD and spec.md are related levels. Every in-scope PRD clause maps to one or more owning ACs through TASKS. Each AC has one owning spec. A clause split across tasks must have every part covered. A spec cannot silently narrow or contradict the registered PRD.

TASKS links task progress instead of copying work checkboxes. TASK links native acceptance instead of duplicating AC tables. Plans reference TASK agreements rather than redefining them. Generated schemas or contracts/ files implement the owning agreement and carry its IF ID and revision.

<a id="document-1-heading-3"></a>

#### 3. Paths and IDs
Recommended repository layout:
```text
docs/tasks/M1/TASKS.md
docs/tasks/M1/M1-001/TASK.md
docs/tasks/M1/M1-SYSTEM/TASK.md
specs/M1-001-slug/{spec.md,plan.md,tasks.md,evidence/}
specs/M1-SYSTEM-slug/{spec.md,plan.md,tasks.md,evidence/}
```
Use qualified IDs: M1-001/AC-001, M1-001/B01, M1-001/V01 and M1-001/T001. Interface IDs are program-wide, such as M1-IF-001@r1. Never reuse retired IDs.

Each TASK has an accountable executor; collaborators may be named. There is no role taxonomy. A task may span modules, and a module may need several tasks. Split by bounded, verifiable behavior and dependencies.

<a id="document-1-heading-4"></a>

#### 4. Preparation before final inputs
Build the document skeleton now. Missing future PRD, architecture, model lists, budgets or thresholds use PENDING_SOURCE, identifying affected work and a resolution condition. They are ordinary preparation states, not a requirement to complete existing teammates' work or run a pilot.

When inputs arrive:
1. Register actual paths, versions, content hashes and sizes.
2. Give source clauses and architecture nodes stable IDs or exact section locators.
3. Allocate every in-scope clause to TASKs and ACs; record exclusions with reasons.
4. Establish dependencies and embed agreements in their owning TASKs.
5. Populate each task's spec, plan, work items and evidence matrix before dependent implementation.
6. Verify the full M1 through the system TASK on an integrated candidate.

Do not fabricate a real task breakdown from absent requirements. The worked example is illustrative. Existing task records remain historical evidence and do not gate this preparation.

<a id="document-1-heading-5"></a>

#### 5. Working loop
1. Locate TASK through TASKS and read its native artifacts and dependencies.
2. Specify observable ACs, failure behavior and applicable nonfunctional thresholds.
3. Plan implementation blocks, affected files, agreements, fixtures and verification methods.
4. Generate native work items and the correspondence matrix. Every AC maps to implementation and verification; every required check has an independent expected outcome.
5. Implement and verify block by block. Preserve evidence, repair failures and follow the dependency graph. Independent blocks can proceed while another is blocked.
6. Connect blocks and verify real provider/consumer boundaries.
7. Verify complete M1 journeys and system constraints through the system TASK.
8. Update the same native records; derive program progress from them.

This is a development loop, not a sequence of approval cards. AI analysis helps detect inconsistencies; runtime evidence establishes behavior.

<a id="document-1-heading-6"></a>

#### 6. Cross-module agreements inside TASK
One TASK owns each interface definition. Its interface section identifies provider and consumer TASKs; input/output structure and semantics; validation; error states; timeout, retry and cancellation; side effects and idempotency; compatibility; and boundary verification. Explain N/A values.

Consumers reference the owner and revision. Avoid parallel definitions. Separate interface-definition dependencies from implementation dependencies to expose and resolve cycles.

Record interface changes in the owning TASK change table, update affected consumers, and invalidate affected evidence. Unknown details block only dependent work.

<a id="document-1-heading-7"></a>

#### 7. Verification and completion
Follow [VERIFICATION.md](#document-2).
- A checked work item means work was done, not that acceptance passed.
- An AC passes only when all mapped required checks have valid PASS evidence.
- A TASK completes when required work, ACs and boundaries pass and no unresolved dependency invalidates the result.
- M1 completes when source allocation is complete, required tasks are verified against the candidate, and its system TASK passes on that same candidate.
- NOT_RUN, BLOCKED, FAIL and STALE are not PASS. Exclusions require a recorded scope basis; they cannot erase a failure.

Completion is based on evidence, without a separate review-and-close stage.

<a id="document-1-heading-8"></a>

#### 8. Large inputs, changes and continuity
Retain the complete 100-200 KB source, but give each feature its relevant clauses, architecture nodes, agreements and surrounding constraints. Do not use summaries as substitutes for source coverage. TASKS detects gaps across the slices.

Use stable locators and revisions so work can resume after a session restart. Maintain an architecture overview and readable module/interaction views linked by node IDs. A diagram alone does not specify interface semantics.

When requirements change, update the baseline and allocation, affected agreements and native artifacts. Record affected AC/block/check IDs and mark their evidence STALE. Ordinary progress changes only tasks.md. Keep previous runs and point to the current effective evidence.

Integrate dependent blocks early. Whole-system acceptance covers the entire M1; smaller implementation units do not reduce that scope.

<a id="document-1-heading-9"></a>

#### 9. Templates and tools
Follow the tables in the [catalog](#document-28). Preserve required fields, use meaningful N/A explanations and record unresolved conditions.

Project native templates live in .specify/templates/overrides/. They replace the optional-testing default for this process. Read [Spec Kit workflow](#document-10) and [Git workflow](#document-11). Generated commands never override an explicit no-commit instruction.

---

<a id="document-2"></a>

## 2. Verification: blocks, boundaries, system

Source: [docs/code/code_sop/VERIFICATION.md](code_sop/VERIFICATION.md)

<a id="document-2-heading-0"></a>

### Verification: blocks, boundaries, system
Version 2, 2026-09-29. This replaces the former testing policy and test-report/checklist workflow. It defines future M1 verification and does not claim application readiness.

<a id="document-2-heading-1"></a>

#### 1. Define a block
A block is bounded behavior with specified inputs, observable outputs or state changes, failure semantics and an executable check. It may be a function, service, workflow step or small connected component. A filename alone is not a block definition.

Define blocks in plan.md and map them to spec.md ACs. Put implementation and verification work in tasks.md; attach results in evidence/. No parallel implementation checklist or report is required.

<a id="document-2-heading-2"></a>

#### 2. Verification levels
| Level | Required conclusion | Representative checks | Limits |
| --- | --- | --- | --- |
| BLOCK | A block implements its required behavior | Normal, boundary and invalid inputs; state invariants; relevant failure and recovery paths | Stubs isolate dependencies but cannot prove real connections |
| BOUNDARY | Connected blocks obey the TASK agreement | Real serialization and semantic fields, compatibility, timeout/error propagation and repeated calls | Fixtures alone cannot prove an external service is available |
| SYSTEM | The integrated candidate satisfies M1 | Complete journeys, applicable persistence/restart, recovery, quality, budgets, cost and latency | A partial demo or green block suite does not prove M1 |

Unit, integration, end-to-end, evaluation, static inspection and reproducible manual checks are methods, not additional workflow stages. Documentation tasks need relevant document checks, not unrelated application tests.

<a id="document-2-heading-3"></a>

#### 3. Define each check before execution
For every V ID, plan.md records level, block/IF IDs, AC references, fixtures, dependency mode (stub/local real/external real), expected outcomes, threshold source, command and working directory or exact manual procedure, prerequisites and retained artifacts.

Select applicable normal, boundary, failure and recovery cases; explain omissions. Expected results must come from requirements or independent fixtures, not a copy of the implementation's algorithm. Prefer a reproducing regression case for a bug.

Missing thresholds, schemas or services remain unresolved. Independent preparation can continue; dependent verification cannot pass.

<a id="document-2-heading-4"></a>

#### 4. Block loop
1. Read the block ACs and interface dependencies.
2. Build the check and implementation in small steps.
3. Execute checks and retain a run record and raw outputs.
4. Link each V/AC row to its evidence in tasks.md.
5. Preserve failures, fix causes and rerun.
6. Connect verified blocks and execute boundary checks.

Tests may precede or accompany implementation. Do not invent failing tests for every document edit. Checks must exercise and assert the target behavior.

<a id="document-2-heading-5"></a>

#### 5. Evidence
Use [EVIDENCE_TEMPLATE](#document-6) in feature evidence/. One run may cover several checks, but each check has its own result.

Record time and run ID; candidate identity; source/spec/plan/IF versions; exact command/procedure and working directory; environment; dependency mode; fixture versions; expected and observed results; exit code; pass/fail/skip counts; raw artifact paths; and limitations.

For uncommitted code, HEAD alone is insufficient: record HEAD, a diff digest and hashes of relevant changed/untracked execution inputs, or an immutable snapshot reference. Include tests, configuration and dependency inputs. Preserve reproducibility without capturing secrets or committing solely to obtain an ID.

<a id="document-2-heading-6"></a>

#### 6. Results
| Result | Meaning |
| --- | --- |
| PASS | Required assertions executed and met expectations on the identified candidate |
| FAIL | A requirement was violated |
| BLOCKED | A prerequisite or unresolved definition prevented verification |
| NOT_RUN | The check has not executed |
| STALE | Earlier evidence no longer covers the current candidate or requirements |
| N/A | Inapplicable with a scope-derived reason; never substitutes for a failed required check |

Zero cases, all-skipped cases, suppressed errors or only stubs cannot establish behavior requiring actual execution or real services. Record skips separately. If a required assertion is skipped, its check is not PASS.

All required V IDs mapped to an AC must have valid PASS evidence. Do not hide mixed outcomes behind a passing average.

<a id="document-2-heading-7"></a>

#### 7. System TASK
TASKS designates one normal TASK for system verification. It has its own spec/plan/tasks/evidence. It owns system ACs and journeys and references child-task coverage without copying their requirements.

Its plan fixes the candidate configuration and component revisions, dependency requirements, complete journeys, datasets and measurable constraints. Its matrix maps system AC -> participating TASK/block/IF IDs -> system V -> evidence.

Before final acceptance, required blocks and interfaces must be ready and their evidence valid for that candidate. Early system runs are useful but do not establish final completion.

Run the assembled product, including applicable cross-module failures and recovery. Missing real accounts/services remain BLOCKED; mock results cannot fill that gap.

<a id="document-2-heading-8"></a>

#### 8. Models and research
Take permitted models from the registered PRD. Never invent model identifiers, role-based selection, providers or evaluation thresholds.

Record provider/model identifiers and available versions, executor inputs, prompts/configuration, datasets and splits, sample counts, repetitions, controllable seeds, scoring rubric, quality metrics and raw outcomes. Cost/latency evidence includes measurement boundaries, retries, concurrency, caching and billing basis.

Use frozen evaluation inputs for comparable runs and define thresholds before final measurements. A single response cannot establish reliability. Stubs can establish routing rules but require separate real-service evidence for live invocation ACs. Disclose uncontrolled variability.

<a id="document-2-heading-9"></a>

#### 9. Revalidation
Behavior, schemas, tests, configuration, dependencies, acceptance and candidate changes trigger an impact assessment. Use TASKS dependencies and TASK agreements to identify affected blocks and downstream consumers. Mark affected matrix rows STALE and rerun their checks and relevant system journeys.

Reuse unchanged evidence only with a recorded comparison establishing equivalent behavior, inputs and dependencies. Evidence-only edits do not inherently require reruns. Keep the reuse basis with the evidence reference.

System completion refers to one exact candidate. After candidate changes, reassess evidence and rerun affected checks before retaining that claim.

<a id="document-2-heading-10"></a>

#### 10. Completion
TASK requires completed required work and valid PASS evidence for every required AC/check, with no invalidating dependency unresolved.

M1 requires all in-scope source clauses allocated, all required TASKs verified for the candidate, consistent interfaces and a passing system TASK on that candidate.

Preparing this framework does not require unfinished teammates' tasks to be completed first.

---

<a id="document-3"></a>

## 3. AI4Research development documentation v2

Source: [docs/code/README.en.md](README.en.md)

<a id="document-3-heading-0"></a>

### AI4Research development documentation v2

**TASKS -> TASK -> one Spec Kit per TASK**, with block verification, boundary verification and whole-system verification.

Start with the [SOP](#document-1), [complete document catalog](#document-28) and [future M1 register](#document-17). Product inputs remain pending; document preparation does not establish M1 implementation or acceptance.

<a id="document-3-heading-1"></a>

#### Common entry points

- [Spec Kit workflow](#document-10)
- [Verification method](#document-2)
- [Git workflow](#document-11)
- [Worked example](#document-18)
- [Migration and preparation](#document-12)

This is the English entry. The English handbook uses this entry throughout; a separate Chinese entry and complete Chinese handbook are available. The process replaces separate authorization, implementation-checklist, review and handoff cards. Historical task evidence is preserved. CODEX_DEMO.md is a historical feature document outside this process package.

The complete ZIP contains guides, templates, examples, repository instructions, native overrides, the constitution and the M1 skeleton. Its manifest records content hashes. Reading and using the package does not require a commit.

<a id="document-3-heading-2"></a>

#### Complete delivery

- [Complete English handbook](AI4Research_Documentation_v2.md)
- [Complete Chinese handbook](AI4Research_Documentation_v2.zh-CN.md)
- [Chinese entry](#document-3)
- [Complete documentation ZIP](AI4Research_Documentation_v2.zip)
- [File manifest](DELIVERY_MANIFEST.json)
- [Documentation checks](#document-29)

---

<a id="document-4"></a>

## 4. TASKS: [PROGRAM-ID]

Source: [docs/code/code_sop/templates/TASKS_TEMPLATE.md](code_sop/templates/TASKS_TEMPLATE.md)

<a id="document-4-heading-0"></a>

### TASKS: [PROGRAM-ID]
Copy to docs/tasks/[PROGRAM-ID]/TASKS.md. This is the program register, not a second implementation checklist.

<a id="document-4-heading-1"></a>

#### 1. Identity and source baselines
| Field | Value |
| --- | --- |
| Program ID and objective | [Fill] |
| Register revision/date | [Fill] |
| Program coordinator | [Name or UNASSIGNED; bookkeeping responsibility, not an approval gate] |
| Full PRD path / revision / SHA256 / bytes | [Fill or PENDING_SOURCE] |
| Architecture source and rendered views / revision / SHA256 | [Fill or PENDING_SOURCE] |
| Scope inclusions and exclusions | [Source references and reasons] |
| System-verification TASK | [Exact TASK link or PENDING_SOURCE] |
| Integrated candidate | [Commit plus dirty-tree identity if needed, or NOT_BUILT] |

<a id="document-4-heading-2"></a>

#### 2. Task register and dependency graph
| TASK ID / entry link | Bounded outcome | Executor | Required for program? | Prerequisite TASK/block/IF IDs | Native feature directory | Progress/evidence source |
| --- | --- | --- | --- | --- | --- | --- |
| [Fill] | [Fill] | [Fill] | [Yes/No with source basis] | [Fill or None] | [Exact path] | [Link to native tasks.md] |

Describe dependency order or add a diagram. Explain and resolve cycles. Progress is read from linked native records; do not duplicate their checkboxes or keep a second task status table.

<a id="document-4-heading-3"></a>

#### 3. Source coverage allocation
| Source clause ID / exact locator | Architecture node/edge IDs | Owning TASK / AC references | Allocation decision and completeness |
| --- | --- | --- | --- |
| [Fill] | [Fill or N/A with reason] | [One or more qualified AC IDs] | [Allocated / PENDING_SOURCE / Unallocated / Excluded with reason] |

Include functional, nonfunctional and system-wide clauses. If a clause spans several ACs, explain coverage of its parts. Each AC has exactly one owning spec. Every in-scope clause must be allocated before claiming program completeness.

<a id="document-4-heading-4"></a>

#### 4. Interface index
| IF ID / revision | Canonical owning TASK section | Provider TASK | Consumer TASKs | Boundary verification location |
| --- | --- | --- | --- | --- |
| [Fill] | [Exact link] | [Fill] | [Fill] | [Qualified V IDs / native evidence matrix] |

This is an index only. The owning TASK defines semantics. Do not repeat schemas here.

<a id="document-4-heading-5"></a>

#### 5. System verification entry
- System TASK and native spec/plan/tasks: [Links].
- Complete journeys and cross-cutting requirements: [References to system ACs, not copies].
- Candidate component/version manifest: [Location].
- Final system run evidence: [Link or NOT_RUN].
- Required child-task evidence for the candidate: [Native links and reuse basis where applicable].
- Program conclusion: [NOT_READY / VERIFYING / VERIFIED; derive from coverage and native evidence].
- Unverified scope and reason: [Fill or None].

VERIFIED requires full source allocation, all required task/block/boundary evidence valid for the candidate, and the system TASK passing on that candidate.

<a id="document-4-heading-6"></a>

#### 6. Source changes and unresolved inputs
| Change/question ID | Source or IF revision / question | Affected TASK/AC/block/check IDs | Action and evidence invalidation | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| [Fill] | [Fill] | [Fill] | [Fill] | [Fill] |

Record material scope decisions here with their source. Unknown future inputs are normal preparation states. Do not create a separate change-request card.

---

<a id="document-5"></a>

## 5. TASK: [TASK-ID] - [Title]

Source: [docs/code/code_sop/templates/TASK_TEMPLATE.md](code_sop/templates/TASK_TEMPLATE.md)

<a id="document-5-heading-0"></a>

### TASK: [TASK-ID] - [Title]
Copy to docs/tasks/[PROGRAM-ID]/[TASK-ID]/TASK.md. TASK is an identity and entry point. Keep acceptance, design, progress and results in the registered Spec Kit artifacts.

The logical TASK includes its Spec Kit artifacts. Physically, spec.md, plan.md and tasks.md are separate linked files, not sections copied into TASK.md.

<a id="document-5-heading-1"></a>

#### 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | [Fill] |
| Parent TASKS | [Exact link] |
| Executor / collaborators | [Fill or UNASSIGNED] |
| Requested outcome and instruction/source | [Bounded purpose and source reference] |
| Included scope / exclusions | [Fill] |
| PRD clause and architecture node references | [IDs/locators and versions] |
| Working checkout / branch / base | [Fill or NOT_STARTED] |
| Affected code/document paths | [Actual paths or PENDING_DESIGN] |

No separate authorization card or review assignment is required. The requested scope applies; material scope changes are recorded below.

<a id="document-5-heading-2"></a>

#### 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | [specs/TASK-ID-slug/] | One directory for this TASK |
| spec.md | [Link] | Requirements, ACs, thresholds |
| plan.md | [Link] | Technical/block design and verification procedures |
| tasks.md | [Link] | Work/progress and evidence correspondence |
| evidence/ | [Path] | Actual verification runs and raw artifacts |
| Supporting artifacts | [Paths or None] | Research, schemas, data models; subordinate to registered authorities |

Do not repeat acceptance tables, work lists or results here.

<a id="document-5-heading-3"></a>

#### 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [Fill or None] | [Fill] | [Fill] | [Fill] |

Separate definition-time dependencies from runtime/implementation dependencies. Continue independent work when one dependency is unresolved.

<a id="document-5-heading-4"></a>

#### 4. Embedded cross-module agreements
For every owned IF, repeat this subsection. For consumed IFs, only link the canonical definition and revision. Use None with reason when there is no boundary.

<a id="document-5-heading-5"></a>

##### [IF-ID] at [revision]
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | [Fill] |
| Purpose / source requirement | [Fill] |
| Inputs: fields, types, units, required/optional, validation | [Fill] |
| Outputs: fields, types, units, semantics, guarantees | [Fill] |
| States and invariants | [Fill] |
| Errors, timeout, retry, cancellation | [Fill or justified N/A] |
| Side effects and idempotency | [Fill or justified N/A] |
| Compatibility and migration | [Version relationship and affected consumers] |
| Machine-readable schema / source path | [Link or None; implements this agreement] |
| Provider/consumer verification responsibilities | [Qualified V IDs and where defined] |
| Open agreement questions | [Fill or None] |

Consumed agreements: [Canonical TASK section links with exact IF revisions; no copied definitions].

<a id="document-5-heading-6"></a>

#### 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| [Fill or None] | [Fill] | [Fill] | [Fill] | [Fill] |

Progress remains in tasks.md. A material source or interface change updates the parent TASKS allocation/index and all affected native references.

---

<a id="document-6"></a>

## 6. Verification run: [RUN-ID]

Source: [docs/code/code_sop/templates/EVIDENCE_TEMPLATE.md](code_sop/templates/EVIDENCE_TEMPLATE.md)

<a id="document-6-heading-0"></a>

### Verification run: [RUN-ID]
Store in the selected feature's evidence/RUN-ID.md. This is observed evidence, not an implementation checklist. One run may cover several checks.

<a id="document-6-heading-1"></a>

#### 1. Execution identity
| Field | Actual value |
| --- | --- |
| TASK ID / run ID / UTC time | [Fill] |
| Level and V IDs | [BLOCK / BOUNDARY / SYSTEM; qualified IDs] |
| Candidate identity | [Commit; for dirty work add diff digest and relevant changed/untracked file hashes or immutable snapshot] |
| Baseline / component revisions | [Fill] |
| PRD, spec, plan and IF versions | [Fill] |
| Working directory / platform / runtime / dependency versions | [Fill] |
| Input/fixture/dataset/model/prompt/configuration versions | [Fill or reasoned N/A] |
| Dependency mode and actual services | [Stub / local real / external real; details] |
| Command or reproducible manual procedure | [Exact invocation/steps; no secret values] |

<a id="document-6-heading-2"></a>

#### 2. Per-check observations
| V ID / AC references | Expected outcome / threshold source | Actual outcome | Exit code / counts including skips | Result | Raw artifact location |
| --- | --- | --- | --- | --- | --- |
| [Fill] | [Fill] | [Actual observation; never planned result] | [Fill or N/A for manual check] | [PASS / FAIL / BLOCKED / NOT_RUN / STALE / N/A] | [Exact path/digest] |

A check is PASS only if all its required assertions actually passed. Empty collection, required skips, missing real dependencies or suppressed errors do not qualify.

<a id="document-6-heading-3"></a>

#### 3. Scope and validity
- Behavior established: [Fill].
- Behavior not established / failures / blockers: [Fill or None].
- Reproducibility details for model/evaluation runs: [Sample count, repetitions, randomness, rubric, variability, cost/latency boundaries or N/A].
- Reused earlier evidence and comparison basis: [Fill or None].
- Superseded run IDs / reason: [Fill or None].
- Follow-up V/work-item references: [Fill or None].
- Candidate/input changes after this run: [None known or impact and STALE references].

Update the native tasks.md matrix to point to this run. Retain earlier runs; do not rewrite their observed outcomes.

---

<a id="document-7"></a>

## 7. Feature Specification: [TASK-ID - FEATURE NAME]

Source: [.specify/templates/overrides/spec-template.md](../../.specify/templates/overrides/spec-template.md)

<a id="document-7-heading-0"></a>

### Feature Specification: [TASK-ID - FEATURE NAME]
**TASK**: [Exact TASK.md link]
**Parent TASKS**: [Exact TASKS.md link]
**Revision / date**: [Fill]
**Feature Branch**: [Actual branch or NOT_STARTED; feature directory does not imply a branch]
**Input**: [Registered PRD clauses and architecture nodes with version and exact locators]
**Status**: [Preparing / Specified; not a runtime result]

<a id="document-7-heading-1"></a>

#### User Scenarios & Testing
<a id="document-7-heading-2"></a>

##### User Story 1 - [Observable outcome] (Priority: P1)
[Describe the user or executor journey.]
**Independent Test**: [Input, observation and expected behavior.]
**Acceptance Scenarios**:
1. Given [state], when [action], then [observable result].
[Add stories as needed. For infrastructure or system-verification tasks, describe the observable consumer/system behavior.]

<a id="document-7-heading-3"></a>

##### Edge Cases
[Applicable invalid/boundary inputs, failure, cancellation, recovery and compatibility cases. Explain omissions.]

<a id="document-7-heading-4"></a>

#### Requirements
<a id="document-7-heading-5"></a>

##### Functional Requirements
- **FR-001**: [Required behavior tied to source clause.]

<a id="document-7-heading-6"></a>

##### Key Entities
[Entities and meaning, or N/A. Interface semantics belong in the owning TASK; reference them.]

<a id="document-7-heading-7"></a>

#### Success Criteria
<a id="document-7-heading-8"></a>

##### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | [Fill] | [Exact behavior/metric; PENDING_SOURCE if unknown] | [BLOCK / BOUNDARY / SYSTEM] |

All required behavior, failure cases and nonfunctional constraints must have AC coverage. Runtime verification is required for behavior changes. Documentation changes use relevant document checks. Test generation must retain these requirements.

<a id="document-7-heading-9"></a>

#### Scope and Assumptions
- Included / excluded scope: [Source-backed boundaries].
- Consumed TASK agreements: [IF IDs, revisions and canonical links].
- Permitted models: [PRD-defined identifiers when relevant; PENDING_SOURCE until available; no invented list].
- Assumptions and unresolved source inputs: [Question, affected ACs and resolution condition, or None].
- System tasks: [Participating task/AC references; own only system-level ACs, do not copy block criteria].

This is the AC authority. Implementation details belong in plan.md; progress and evidence links belong in tasks.md.

---

<a id="document-8"></a>

## 8. Implementation Plan: [TASK-ID - FEATURE]

Source: [.specify/templates/overrides/plan-template.md](../../.specify/templates/overrides/plan-template.md)

<a id="document-8-heading-0"></a>

### Implementation Plan: [TASK-ID - FEATURE]
**TASK**: [Exact link] | **Spec**: [Exact link / revision]
**Revision / date**: [Fill] | **Branch**: [Actual branch]
**Input sources**: [PRD/architecture revisions and relevant locators]

<a id="document-8-heading-1"></a>

#### Summary
[Approach, scope and key technical decisions. Reference ACs.]

<a id="document-8-heading-2"></a>

#### Technical Context
- Language/runtime, dependencies, platform, storage: [Confirmed values or unresolved].
- Model/provider configuration if relevant: [PRD-defined choices].
- Environment and actual command entry points: [Paths; mark unconfirmed commands].
- Performance/quality/resource constraints: [AC references; do not redefine thresholds].

<a id="document-8-heading-3"></a>

#### Constitution Check
Confirm TASKS/TASK/feature linkage, single authorities, embedded agreement references, complete AC/block/check mapping, scope and truthful evidence. Record unresolved items and affected work. This is a consistency check, not a human approval stage.

<a id="document-8-heading-4"></a>

#### Project Structure
[Actual affected source/test/configuration paths and native supporting artifacts. Do not invent an implementation directory from a module name.]

<a id="document-8-heading-5"></a>

#### Blocks and Dependencies
| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | [Fill] | [Fill] | [Fill or None] | [Fill] |

[Dependency order or graph. Identify shared files. Definition-time dependencies and runtime dependencies may differ.]

<a id="document-8-heading-6"></a>

#### Interfaces and Technical Decisions
- Owned/consumed IF revisions and canonical TASK section links: [Fill].
- Data model, storage, failure handling and recovery: [Fill or justified N/A].
- Alternatives and significant decisions: [Decision, reason and implications].
- Generated schemas/contracts: [Implement owning TASK agreements; no parallel normative definitions].

<a id="document-8-heading-7"></a>

#### Verification Design
| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | [BLOCK/BOUNDARY/SYSTEM] | [Qualified references] | [Fill] | [AC link] | [Exact entry or PENDING_DESIGN] | [Fill] |

Define relevant normal, boundary, failure and recovery checks. Distinguish real connections from stubs. For models, define dataset versions, metrics, repetitions and measurement procedure; thresholds stay in spec.md.

<a id="document-8-heading-8"></a>

#### System Candidate and Journeys
[For system TASK: component revisions/configuration manifest, complete journey sequence, participating blocks/interfaces, real service requirements and evidence-validity rules. Otherwise reference the system TASK and expected contribution.]

<a id="document-8-heading-9"></a>

#### Unresolved Decisions and Impact
[Question, affected block/check, resolution condition. Scope/IF changes link TASK change entries. Revalidation follows the dependency graph.]

---

<a id="document-9"></a>

## 9. Tasks: [TASK-ID - FEATURE]

Source: [.specify/templates/overrides/tasks-template.md](../../.specify/templates/overrides/tasks-template.md)

---
description: "TASK-native work and acceptance/evidence correspondence"
---
<a id="document-9-heading-0"></a>

### Tasks: [TASK-ID - FEATURE]
**TASK**: [Exact link] | **Spec / Plan revisions**: [Fill]
**Feature directory**: [Exact registered path]

Verification work is required as defined in spec.md and plan.md. This is the only implementation work list. Do not generate a separate implementation checklist, authorization, review or handoff card.

<a id="document-9-heading-1"></a>

#### Work Items
Format: `- [ ] T001 [P?] [US1] Description; block/AC/V references; actual path`.
[P] requires disjoint changes and satisfied dependencies; it is not permission to spawn agents or publish.

<a id="document-9-heading-2"></a>

##### Foundation / shared definitions
- [ ] T001 [US1] [Prepare required fixtures/interfaces/environment; references and paths]

<a id="document-9-heading-3"></a>

##### Block B01 - [Name]
- [ ] T002 [US1] [Implement bounded behavior; B01, AC-001; actual code path]
- [ ] T003 [US1] [Execute block verification V01 and retain run evidence; actual check path]

<a id="document-9-heading-4"></a>

##### Connected boundaries
- [ ] T004 [US1] [Execute V02 against actual connected blocks; IF reference and check path]

<a id="document-9-heading-5"></a>

##### System contribution
- [ ] T005 [US1] [Integrate and execute task's required system contribution, or link the system TASK work; actual path]

Replace sample items with the task's real dependency order. For the system TASK, define its candidate preparation and complete journey checks here. A checked work item means that operation was performed, not that its AC passed.

<a id="document-9-heading-6"></a>

#### Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | B01 | T002 | V01 / T003 | NOT_RUN | None | Initial |

Add rows as needed so every required V has an unambiguous result. Every AC must be covered; every V maps back to ACs. Do not mark an AC passed when one required check is FAIL, BLOCKED, NOT_RUN or STALE.

<a id="document-9-heading-7"></a>

#### Dependency Order and Execution Notes
[Order, unresolved prerequisites, shared-file constraints, resumable next action. Do not duplicate the work list.]

<a id="document-9-heading-8"></a>

#### Current Verification Conclusion
- Candidate identity: [Exact identity or NOT_BUILT].
- Required work complete: [Derive from work items].
- Required AC/check coverage: [Derived matrix summary].
- Conclusion: [NOT_READY / IN_PROGRESS / BLOCKED / VERIFIED].
- Remaining limitations and next work IDs: [Fill or None].

VERIFIED requires all required work complete, all required checks PASS with valid evidence for the candidate and no invalidating dependency. System TASK completion does not by itself establish program completeness without TASKS source coverage.

<a id="document-9-heading-9"></a>

#### Evidence Invalidation
[Changed source/IF/code/configuration/test/dependency IDs, affected rows, new required runs or explicit unchanged-evidence reuse basis. Keep prior run records.]

---

<a id="document-10"></a>

## 10. Spec Kit workflow for TASKS / TASK

Source: [docs/code/code_sop/SPEC_KIT_WORKFLOW.md](code_sop/SPEC_KIT_WORKFLOW.md)

<a id="document-10-heading-0"></a>

### Spec Kit workflow for TASKS / TASK
<a id="document-10-heading-1"></a>

#### 1. Tool and task identity
The repository has Spec Kit 1.0.12 installed. Existing installation details are in docs/governance/ENVIRONMENT.md; they are historical environment facts, not readiness gates for future M1.

One checkout has one installation and many feature directories. One TASK owns one feature directory. Start from TASKS -> TASK, never from a guessed branch name.

Before native commands, select the exact registered directory:
```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'specs/M1-001-example'
git status --short --branch
```
Replace the example with the actual TASK path. Environment selection has priority over the local .specify/feature.json pointer. Feature selection is not a branch switch. Do not run two feature-generating sessions in one checkout concurrently; use isolated checkouts for concurrent task work.

<a id="document-10-heading-2"></a>

#### 2. Project templates
The local resolver gives .specify/templates/overrides/ priority over installed templates. This package supplies spec-template.md, plan-template.md and tasks-template.md there.

Use these overrides rather than copying old DESIGN/PLAN templates. Installed vendor core templates and skills remain unchanged; a tool upgrade must preserve and re-check the project overrides.

Read-only resolver check from the repository root:
```powershell
& .\.specify\scripts\powershell\resolve-template.ps1 spec-template -Json
& .\.specify\scripts\powershell\resolve-template.ps1 plan-template -Json
& .\.specify\scripts\powershell\resolve-template.ps1 tasks-template -Json
```

<a id="document-10-heading-3"></a>

#### 3. Native command sequence
| Command | Inputs and output | Project requirement |
| --- | --- | --- |
| $speckit-specify | Allocated PRD clauses -> native spec.md | Preserve source locators, AC IDs and required verification |
| $speckit-clarify | Unresolved spec inputs -> clarified spec | Ask only about real missing information; independent preparation can continue |
| $speckit-plan | Spec and TASK agreements -> native plan.md | Define blocks, dependencies and verification procedures |
| $speckit-tasks | Spec and plan -> native tasks.md | Include verification work and the AC/block/check/evidence matrix |
| $speckit-analyze | Cross-artifact consistency findings | Diagnostic only; resolve issues in authoritative artifacts |
| $speckit-implement | Ordered work -> code, checks and evidence | Follow block dependencies and update the same native records |
| $speckit-converge | Optional further gap detection | New findings become native work items within the TASK scope |

The $speckit command names above are invocation names, not PowerShell executables. Use the installed agent integration.

Spec Kit's built-in requirements checklist is a generated specification diagnostic. It is not the removed implementation checklist. Do not add a custom checklist workflow, reviewer assignment, separate authorization card or human-review gate. Resolve diagnostic findings in spec/plan/tasks; missing definitions constrain dependent work, not unrelated preparation.

The upstream implementation skill may suggest pausing on checklist markers or committing work. The user's v2 instruction explicitly removes the parallel gating process. Include the project instruction below when invoking native skills. These are project workflow instructions, not a claim that vendor skill code has been rewritten.

<a id="document-10-heading-4"></a>

#### 4. Reusable invocation context
```text
Work under Code SOP v2. TASK: <exact path>; parent TASKS: <exact path>;
feature directory: <exact registered path>. Read its registered source clauses,
TASK interface agreements and project native overrides.
Use spec.md for ACs, plan.md for blocks/procedures and tasks.md for all work
and AC-to-evidence mapping. Required block/boundary/system verification is
explicitly requested. Generated quality findings are diagnostic: resolve
them in those files; do not add an implementation checklist, reviewer gate,
write_code card, test-report card or handoff card.
Respect the user's current action scope and no-commit/no-push instructions.
```

<a id="document-10-heading-5"></a>

#### 5. Large PRDs and generated support files
TASKS covers the complete source. Each task receives its assigned source clauses, relevant global constraints, architecture views and provider/consumer agreements. A summary alone is insufficient. Verify that every AC has a source and every allocated clause has AC coverage.

Research, data-model, quickstart and generated schema files are optional support. Normative cross-module behavior stays in the owning TASK. Generated contracts/ files carry the IF revision they implement.

After generation, verify required sections and matrix columns. Regenerating tasks.md must preserve completed work and evidence or explicitly migrate them; do not overwrite run history.

<a id="document-10-heading-6"></a>

#### 6. Resuming and blocked inputs
Resume through TASKS -> TASK -> selected feature -> native tasks.md next action. Read the matrix and unresolved dependencies, not a second status report.

PENDING_SOURCE is allowed while the future PRD/architecture is being written. Do not fabricate models, contracts or thresholds to complete a template. Block only work whose correctness depends on the missing input.

<a id="document-10-heading-7"></a>

#### 7. Hooks and external actions
Inspect actual hooks before execution. This process does not enable automatic branch/commit/PR extensions. No generated hook or recommendation overrides a user instruction. Commit, push, merge, messaging and deployment follow the user's action scope, not a checklist result.

---

<a id="document-11"></a>

## 11. Git and integration

Source: [docs/code/code_sop/GIT_WORKFLOW.md](code_sop/GIT_WORKFLOW.md)

<a id="document-11-heading-0"></a>

### Git and integration
This is a supporting transport guide, not a review/authorization workflow.

<a id="document-11-heading-1"></a>

#### Branches
The team integration branch is ai4r_main_branch. Persistent personal branches are ai4r_xiaoyang, ai4r_saurav, ai4r_ramika and ai4r_muk. Record actual checkout, branch and baseline in TASK.

Keep unrelated task changes separable. Concurrent tasks may use task branches and isolated checkouts. A feature-directory name does not change the Git branch. Preserve existing work before switching, synchronizing or resolving conflicts.

<a id="document-11-heading-2"></a>

#### Read-only inspection
Run from the actual checkout:
```powershell
git status --short --branch
git diff --stat
git diff --check
git rev-parse HEAD
```
The local repository used for this package is D:\research\ai_for_research\jiuwenswarm. Do not infer a clean tree or a synchronized remote from a template.

<a id="document-11-heading-3"></a>

#### Integration and evidence
Use the registered TASK scope and Spec Kit work list. Integrate dependent blocks into an identifiable candidate and run the required boundary/system checks.

For commits or PRs when requested, link TASK, describe the behavior and point to native tasks.md evidence. Do not maintain a separate PR-template/checklist authority. The intended team PR base is ai4r_main_branch; inspect the actual target.

Conflict resolutions and base changes can invalidate evidence. Assess affected blocks and downstream journeys, then rerun checks as defined by VERIFICATION.md. Never assume that passing on a feature branch proves the combined candidate.

<a id="document-11-heading-4"></a>

#### No automatic commits
Commands, generated work items and hooks do not require commits. Honor a no-commit instruction, including during synchronization steps that could create merge commits. Record uncommitted candidate identity using the evidence rules.

Do not discard local changes, force-push shared branches or rewrite history to simplify integration. Recovery of data or external side effects may require more than reverting code; represent needed recovery work in the same TASK/Spec Kit system.

---

<a id="document-12"></a>

## 12. v2 preparation and migration

Source: [docs/code/code_sop/MIGRATION.md](code_sop/MIGRATION.md)

<a id="document-12-heading-0"></a>

### v2 preparation and migration
<a id="document-12-heading-1"></a>

#### Intended state
This work prepares the process before the complete M1 PRD and architecture arrive. Existing teammates' implementation is unfinished; that is not a defect to repair as part of documentation preparation. No pilot or reviewer staffing is required to adopt this document structure.

<a id="document-12-heading-2"></a>

#### Replacement map
| Former artifact/process | v2 home |
| --- | --- |
| TASK card plus separate authorization | TASK identity, requested scope and source |
| Manual DESIGN and PLAN | Native plan.md |
| Separate contract / ADR / architecture task records | Embedded TASK agreements and native plan decisions; master architecture remains a source |
| Implementation checklist | Removed; native tasks.md is the only work list |
| TESTING policy and TEST_REPORT cards | Rebuilt VERIFICATION.md, plan procedures, native evidence matrix and feature evidence/ |
| AI/human review card and closing gate | Removed from the task lifecycle |
| HANDOFF and CURRENT_STATUS task copies | TASK entry point and native resumable work/evidence |
| CHANGE_REQUEST | TASK changes and TASKS source-impact entries |
| Ownership, file-map and environment cards per task | TASK executor/scope and plan technical context |
| Adoption checklist and kickoff pack | Current package catalog and future-M1 skeleton |

The removed templates and protocols are deleted from the active docs/code package. Historical records in docs/tasks/AI4R-001 and existing application test code are preserved. Their old process text is not a requirement for new v2 tasks.

<a id="document-12-heading-3"></a>

#### Prepared now
- Program/task/evidence templates.
- Native spec/plan/tasks overrides.
- Block, boundary and system verification method.
- Updated root instructions and constitution.
- A clearly fictional end-to-end documentation example.
- A future-M1 TASKS skeleton with pending source inputs.
- A complete English delivery bundle and manifest.

<a id="document-12-heading-4"></a>

#### When final inputs arrive
Register exact PRD/architecture paths and baselines in M1 TASKS. Allocate real source clauses, create real TASK cards and their feature directories, and designate the system TASK. Extract the model list from the PRD; do not reuse example names as requirements.

Bind commands and thresholds to actual code and requirements. Unknown values remain explicit until needed. Do not create speculative implementation tasks merely to fill an empty register.

<a id="document-12-heading-5"></a>

#### Existing work
Continuing an existing task does not require retroactive duplication. When moving it to v2, preserve its native work IDs and evidence, register it under a TASKS, fold still-relevant boundary definitions into TASK, and record old artifact paths as historical references. Do not relabel incomplete tests as passing or rewrite earlier execution history.

The current legacy status/environment documents may remain as historical context. New M1 progress lives in its native task records through TASKS.

<a id="document-12-heading-6"></a>

#### Tool maintenance
Project overrides are separate from installed vendor templates and skills. Root instructions and invocation context establish the requested v2 behavior. No application implementation, test-suite replacement or remote repository configuration is performed by this documentation package.

The package is usable while product inputs are pending; completeness of future M1 implementation is a separate evidence-based condition.

---

<a id="document-13"></a>

## 13. Repository AGENTS template for SOP v2

Source: [docs/code/AGENTS_global.md](AGENTS_global.md)

<a id="document-13-heading-0"></a>

### Repository AGENTS template for SOP v2
Integrate into the repository root, preserving applicable implementation constraints.

<a id="document-13-heading-1"></a>

#### Entry points
- Policy: docs/code/Code_SOP.md.
- Program entry: docs/tasks/<PROGRAM-ID>/TASKS.md.
- Task entry: docs/tasks/<PROGRAM-ID>/<TASK-ID>/TASK.md.
- Spec Kit workflow: docs/code/code_sop/SPEC_KIT_WORKFLOW.md.
- Verification: docs/code/code_sop/VERIFICATION.md.
- Constitution: .specify/memory/constitution.md.

<a id="document-13-heading-2"></a>

#### Durable rules
1. Start with TASKS -> TASK -> the exact registered feature directory. Read applicable subtree AGENTS and existing callers/tests before implementation.
2. TASKS owns source allocation and dependencies. TASK owns identity, scope and interface agreements. Native spec, plan and tasks own acceptance, design and work/evidence correspondence respectively.
3. Each TASK has an executor and one Spec Kit directory. Do not create separate authorization, implementation-checklist, review, handoff or test-report cards.
4. Cross-module definitions live in one owning TASK; consumers reference IF ID/revision. Generated schemas implement that agreement.
5. Implement and verify block by block, verify connected boundaries, then verify the whole candidate through a system TASK.
6. Preserve evidence and distinguish PASS, FAIL, BLOCKED, NOT_RUN, STALE and N/A. Checkboxes alone never prove acceptance.
7. Missing future PRD/architecture inputs do not stop unrelated preparation. Never invent models, thresholds or schemas.
8. Select the feature explicitly; isolate concurrent generation. Read project overrides and include the v2 invocation context when using native skills.
9. Generated requirements-quality checklists are diagnostic and must not restore the removed approval/reviewer process. Resolve their findings in native artifacts.
10. Update affected source mappings, IF references and evidence after material changes. Ordinary progress updates only native tasks.md.
11. Preserve unrelated work and credentials. Follow actual user authorization for external actions; never auto-commit or bypass a no-commit instruction.
12. Read the relevant template and retain its required fields and matrices. Explain N/A and unresolved conditions.

---

<a id="document-14"></a>

## 14. Module/subtree AGENTS template

Source: [docs/code/AGENTS_local.md](AGENTS_local.md)

<a id="document-14-heading-0"></a>

### Module/subtree AGENTS template
Deploy only after confirming the actual code path; preserve existing subtree constraints.

<a id="document-14-heading-1"></a>

#### Context
- Scope and exclusions: [Actual paths and responsibilities].
- Parent AGENTS: [Actual paths].
- Program TASKS and current TASK: [Links].
- Executor: [Name or task reference].
- Native feature: [Exact path from TASK].
- Relevant architecture source nodes: [References].
- Owned/consumed agreements: [Owning TASK links and IF revisions].

<a id="document-14-heading-2"></a>

#### Local invariants
[Behavior, state, persistence, compatibility and resource constraints. Do not invent interfaces from a module name.]

<a id="document-14-heading-3"></a>

#### Work and verification
Read existing code/callers/tests. Plan observable blocks in native plan.md and track all implementation/verification work in native tasks.md. Verify normal, boundary and relevant failure paths, then actual connected boundaries and the system contribution.

Commands, working directories, fixtures and thresholds are registered in the current native plan/spec. Actual outputs belong in feature evidence/ and are linked from the native matrix. No separate review, checklist, authorization or handoff record is required.

Keep task progress out of AGENTS. Update this file only for durable local constraints and entry points. Respect user scope, preserve credentials/unrelated work, and do not auto-commit.

---

<a id="document-15"></a>

## 15. AI4Research Repository Instructions

Source: [AGENTS.md](../../AGENTS.md)

<a id="document-15-heading-0"></a>

### AI4Research Repository Instructions
Maintainer: Xiaoyang. These durable instructions apply throughout the repository; existing code-subtree instructions remain applicable.

<a id="document-15-heading-1"></a>

#### Entry points
- [Code SOP v2](#document-1)
- [Future M1 TASKS](#document-17)
- [Spec Kit workflow](#document-10)
- [Verification method](#document-2)
- [Constitution](#document-16)
- Historical environment facts: docs/governance/ENVIRONMENT.md.
- Historical task: docs/tasks/AI4R-001/TASK.md; it is not the future-M1 register.

<a id="document-15-heading-2"></a>

#### Working rules
1. Follow TASKS -> TASK -> one registered Spec Kit directory per TASK. Read applicable AGENTS, the exact source clauses, agreements, native spec/plan/tasks and existing callers/tests before implementation.
2. TASKS owns source allocation and task dependencies. TASK owns identity, executor, scope and cross-module agreements. spec.md owns ACs; plan.md owns technical/block design and verification procedures; tasks.md owns work/progress and AC-to-evidence correspondence.
3. Do not create separate write_code, implementation checklist, test-report, review, handoff or change-request cards. The user's requested scope is recorded in TASK. This v2 process has no reviewer-assignment or approval gate.
4. A cross-module agreement has one owning TASK and a stable IF ID/revision. Consumers and generated schemas reference it.
5. Implement and verify blocks, verify connected boundaries, and then verify the complete integrated system. Use current evidence, not checklist completion or generated analysis, to claim acceptance.
6. Record exact candidates, commands, environments, fixtures, expected/observed outcomes and limitations. Required skips, missing services, stale evidence and unrun checks are not passes.
7. Future PRD/architecture/model/threshold inputs may be PENDING_SOURCE. Continue independent preparation and constrain only affected work. Do not fabricate product requirements.
8. Select the exact feature directory before native commands. Isolate concurrent generation; a local feature pointer is not a task lock.
9. Read project overrides in .specify/templates/overrides/ and use the v2 invocation context. Installed skill suggestions about optional tests, reviewer-owned checklists or auto-commits do not reintroduce processes the user explicitly removed. Resolve quality findings in native artifacts; preserve diagnostic truth.
10. Material source/interface changes update TASKS/TASK and affected native records, and invalidate affected evidence. Ordinary progress changes only tasks.md.
11. Preserve unrelated work, existing implementation constraints and credentials. Follow user authorization for external actions. Do not commit, push, merge or deploy merely because a generated task or hook suggests it. Explicit no-commit instructions also exclude merges that would create commits.
12. Read and follow the relevant templates, retaining required fields and matrices. Record unresolved conditions and justified N/A values instead of invented facts.

<a id="document-15-heading-3"></a>

#### Existing code-subtree instructions
For web changes, read jiuwenswarm/channels/web/AGENTS.md and the frontend AGENTS.md. Trajectory changes also require its subtree instructions. Preserve frontend test identifiers, shared settings layout, supported browser compatibility, localization and applicable visual/build verification.

A feature request permits necessary functional changes; the older test-ID-only instruction applies to a test-ID-only pass and does not cancel explicitly requested feature work. Apply its naming rules to touched controls.

<a id="document-15-heading-4"></a>

#### Legacy evidence
Existing task histories and application tests are preserved. New v2 tasks do not require legacy authorization/review cards or completion of unfinished legacy tasks. Do not rewrite past run results when referencing them.

---

<a id="document-16"></a>

## 16. AI4Research Constitution

Source: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)

<a id="document-16-heading-0"></a>

### AI4Research Constitution
Version 2.0.0 | Updated 2026-09-29 | Source: the user's requested TASKS/TASK/Spec Kit redesign.

<a id="document-16-heading-1"></a>

#### I. One hierarchy
TASKS describes the whole program; TASK is identity and entry; every TASK has exactly one Spec Kit feature directory. An executor carries task responsibility without a separate role taxonomy.

<a id="document-16-heading-2"></a>

#### II. One authority per fact
TASKS owns sources/allocation/dependencies. TASK owns identity/scope/interfaces. Native spec.md owns acceptance, plan.md owns design/procedures, tasks.md owns work/progress/evidence correspondence. Evidence records actual runs.

No separate coding-authorization, implementation-checklist, test-report, review, handoff or change-request card is required.

<a id="document-16-heading-3"></a>

#### III. Embedded agreements
Cross-module agreements have one canonical TASK section, IF ID and revision. Consumers reference that definition. Generated contracts and schemas implement it.

<a id="document-16-heading-4"></a>

#### IV. Block-to-system verification
Implement and verify bounded blocks, verify actual connected boundaries, then verify the whole integrated candidate through a system TASK. All required ACs have mapped checks and valid evidence. Required verification is explicitly requested in every generated work list.

<a id="document-16-heading-5"></a>

#### V. Truthful and current evidence
Checkboxes and analysis do not prove behavior. Retain failures and limitations. Distinguish PASS, FAIL, BLOCKED, NOT_RUN, STALE and N/A. Identify the exact tested tree, including relevant uncommitted inputs; never commit solely for evidence identity.

<a id="document-16-heading-6"></a>

#### VI. Preparation and change
Missing future product inputs remain PENDING_SOURCE and constrain only dependent work. Scope/interface changes update their authorities and invalidate affected evidence. Existing unfinished work and a pilot are not prerequisites to prepare this framework.

<a id="document-16-heading-7"></a>

#### VII. User scope and tooling
Read applicable AGENTS and project overrides. Generated diagnostic checklists do not establish a human-review or authorization gate. Explicit user scope and no-commit instructions apply to commands and hooks. Preserve unrelated work and secrets.

<a id="document-16-heading-8"></a>

#### Governance
This constitution implements SOP v2. It replaces the prior review/authorization-centered constitution. Native artifacts retain these principles; upstream templates/skills are tooling and do not override the user's requested process. Document revisions do not claim application readiness or remote enforcement.

---

<a id="document-17"></a>

## 17. TASKS: M1

Source: [docs/tasks/M1/TASKS.md](../tasks/M1/TASKS.md)

<a id="document-17-heading-0"></a>

### TASKS: M1
Prepared on 2026-09-29 under SOP v2. This is the future full-product M1 register, separate from historical AI4R-001 milestone naming.

<a id="document-17-heading-1"></a>

#### 1. Identity and source baselines
| Field | Value |
| --- | --- |
| Program ID and objective | M1: implement the full milestone described by the forthcoming master PRD and architecture |
| Register revision/date | r1 / 2026-09-29 |
| Program coordinator | UNASSIGNED; does not block document preparation |
| Full PRD path / revision / SHA256 / bytes | PENDING_SOURCE; anticipated size 100-200 KB, not yet registered |
| Architecture source and rendered views / revision / SHA256 | PENDING_SOURCE |
| Scope inclusions and exclusions | PENDING_SOURCE; no invented exclusions |
| System-verification TASK | PENDING_SOURCE; designate after the actual task breakdown |
| Integrated candidate | NOT_BUILT for this future program |

<a id="document-17-heading-2"></a>

#### 2. Task register and dependency graph
| TASK ID / entry link | Bounded outcome | Executor | Required for program? | Prerequisite TASK/block/IF IDs | Native feature directory | Progress/evidence source |
| --- | --- | --- | --- | --- | --- | --- |

No real child TASKs are registered yet. Populate from the master inputs; one TASK gets one feature directory. Native tasks.md owns progress. The package's DEMO example is not an M1 task.

Dependency graph: PENDING_SOURCE. Model Router is one anticipated part of the full scope; its detailed decomposition must follow the final inputs.

<a id="document-17-heading-3"></a>

#### 3. Source coverage allocation
| Source clause ID / exact locator | Architecture node/edge IDs | Owning TASK / AC references | Allocation decision and completeness |
| --- | --- | --- | --- |
| Master PRD not yet supplied | Master architecture not yet supplied | Not allocated | PENDING_SOURCE |

Every in-scope clause must be assigned when the source arrives. A large PRD may be read in slices, but this register must account for its whole scope.

<a id="document-17-heading-4"></a>

#### 4. Interface index
| IF ID / revision | Canonical owning TASK section | Provider TASK | Consumer TASKs | Boundary verification location |
| --- | --- | --- | --- | --- |

PENDING_SOURCE. Agreements will live inside the owning TASK, not in separate contract cards.

<a id="document-17-heading-5"></a>

#### 5. System verification entry
- System TASK and native spec/plan/tasks: PENDING_SOURCE.
- Journeys and system requirements: PENDING_SOURCE.
- Candidate component/version manifest: NOT_BUILT.
- Final system run evidence: NOT_RUN.
- Child-task evidence for the candidate: None yet.
- Program conclusion: NOT_READY for implementation acceptance; document preparation is available.
- Unverified scope: the complete future M1.

<a id="document-17-heading-6"></a>

#### 6. Source changes and unresolved inputs
| Change/question ID | Source or IF revision / question | Affected TASK/AC/block/check IDs | Action and evidence invalidation | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| INPUT-001 | Full master PRD | To be allocated | Register actual file/version/hash, then map all clauses | Unassigned; resolve when master PRD is supplied |
| INPUT-002 | Master architecture and node IDs | To be allocated | Register source/views; resolve task boundaries and dependencies | Unassigned; resolve when architecture is supplied |
| INPUT-003 | Permitted model identifiers and executor-only routing inputs | Future Router TASKs | Extract exact model list from PRD; retain the user's removal of role | Future Router executor; resolve from registered PRD |
| INPUT-004 | System journeys and measurable thresholds | Future system TASK | Derive from PRD; define checks before final measurements | Future system executor; resolve from registered PRD |

No existing teammate task must finish before this skeleton can be used. No pilot, reviewer assignment or commit is required by this register.

---

<a id="document-18"></a>

## 18. Worked example: one small program, two TASKs

Source: [docs/code/code_sop/WORKED_EXAMPLE.md](code_sop/WORKED_EXAMPLE.md)

<a id="document-18-heading-0"></a>

### Worked example: one small program, two TASKs
This is a fictional, unexecuted documentation example. It is not the M1 PRD, Router design, model list or a report of passing tests.

Open [DEMO TASKS](#document-19). It allocates a tiny source to:
- [DEMO-001](#document-20): validate and normalize an executor label.
- [DEMO-SYSTEM](#document-21): wire a consumer and verify the complete request-to-display journey.

Each has its own spec/plan/tasks directory. The provider owns one embedded IF agreement; the consumer references it. DEMO-001's native matrix covers two blocks and the connection check; the system TASK's matrix covers whole-journey results.

Expected values illustrate test design only. Every runtime check remains NOT_RUN. No application files or tests are created by this example.

<a id="document-18-heading-1"></a>

#### Walkthrough
1. TASKS allocates each SOURCE clause to a single owning spec/AC.
2. TASK binds the executor, source and feature paths, and owns or consumes IF-001@r1.
3. spec.md defines behavior, including rejected inputs.
4. plan.md defines B01 validation, B02 normalization, connection checks and exact expected values.
5. tasks.md contains implementation/verification work and its evidence matrix.
6. An eventual execution creates evidence from the shared evidence template and updates the matrix.
7. A passing block result alone cannot complete DEMO: the boundary and system checks must also pass on the candidate.

The example has no write_code, implementation checklist, test report, review or handoff file.

---

<a id="document-19"></a>

## 19. TASKS: DEMO

Source: [docs/code/code_sop/examples/DEMO/TASKS.md](code_sop/examples/DEMO/TASKS.md)

<a id="document-19-heading-0"></a>

### TASKS: DEMO
Illustrative only. No runtime execution has occurred.

<a id="document-19-heading-1"></a>

#### 1. Identity and source baselines
| Field | Value |
| --- | --- |
| Program ID and objective | DEMO: normalize an executor label and show it to a consumer |
| Register revision/date | r1 / 2026-09-29 |
| Program coordinator | Unassigned example |
| Full PRD path / revision / SHA256 / bytes | The three inline SOURCE clauses below, r1; hash/bytes N/A for an inline fictional source |
| Architecture source and rendered views / revision / SHA256 | Inline r1: request -> validate -> normalize -> consumer display; hash N/A |
| Scope inclusions and exclusions | Three SOURCE clauses; external services, storage, model routing and performance claims excluded |
| System-verification TASK | [DEMO-SYSTEM](#document-21) |
| Integrated candidate | NOT_BUILT |

Fictional source:
- SOURCE-01: a label is a string containing at least one non-whitespace character; other values produce INVALID_LABEL.
- SOURCE-02: return the label trimmed and lowercased.
- SOURCE-03: the full request displays the normalized label on success and INVALID_LABEL on invalid input, with no stale success value.

<a id="document-19-heading-2"></a>

#### 2. Task register and dependency graph
| TASK ID / entry link | Bounded outcome | Executor | Required for program? | Prerequisite TASK/block/IF IDs | Native feature directory | Progress/evidence source |
| --- | --- | --- | --- | --- | --- | --- |
| [DEMO-001](#document-20) | Validate and normalize labels | Unassigned example | Yes | None for block work; consumer needed for boundary V03 | specs/DEMO-001-label/ within this example | [tasks](#document-24) |
| [DEMO-SYSTEM](#document-21) | Consumer wiring and system verification | Unassigned example | Yes | DEMO-001 blocks and IF-001@r1 | specs/DEMO-SYSTEM-journey/ within this example | [tasks](#document-27) |

Order: define IF -> provider blocks -> consumer wiring -> boundary check -> final system check. The provider boundary check depends on consumer wiring, not on the system TASK being fully complete; this avoids a circular completion dependency.

<a id="document-19-heading-3"></a>

#### 3. Source coverage allocation
| Source clause ID / exact locator | Architecture node/edge IDs | Owning TASK / AC references | Allocation decision and completeness |
| --- | --- | --- | --- |
| SOURCE-01 | Validate | DEMO-001/AC-001 | Allocated: validity and error result |
| SOURCE-02 | Normalize | DEMO-001/AC-002 | Allocated: output transformation |
| SOURCE-03 | Provider -> consumer display | DEMO-SYSTEM/AC-001, AC-002 | Allocated: success and invalid-input journeys |

<a id="document-19-heading-4"></a>

#### 4. Interface index
| IF ID / revision | Canonical owning TASK section | Provider TASK | Consumer TASKs | Boundary verification location |
| --- | --- | --- | --- | --- |
| IF-001@r1 | [Owning TASK](#document-20-heading-4) | DEMO-001 | DEMO-SYSTEM | DEMO-001/V03 |

<a id="document-19-heading-5"></a>

#### 5. System verification entry
- Native spec/plan/tasks: [System TASK registry](#document-21-heading-2).
- Complete journeys: DEMO-SYSTEM/AC-001 and AC-002.
- Candidate manifest: NOT_BUILT; eventual run records provider and consumer source hashes.
- Final run evidence: NOT_RUN.
- Required child evidence: DEMO-001/V01, V02 and V03 valid for that candidate.
- Program conclusion: NOT_READY.
- Unverified scope: all runtime behavior.

<a id="document-19-heading-6"></a>

#### 6. Source changes and unresolved inputs
| Change/question ID | Source or IF revision / question | Affected TASK/AC/block/check IDs | Action and evidence invalidation | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 | No implementation exists | All | Keep checks NOT_RUN; bind actual paths if instantiated | Unassigned; only if this toy example is explicitly selected for implementation |

---

<a id="document-20"></a>

## 20. TASK: DEMO-001 - Normalize executor labels

Source: [docs/code/code_sop/examples/DEMO/DEMO-001/TASK.md](code_sop/examples/DEMO/DEMO-001/TASK.md)

<a id="document-20-heading-0"></a>

### TASK: DEMO-001 - Normalize executor labels
Fictional example; implementation is not requested.

<a id="document-20-heading-1"></a>

#### 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | DEMO-001 / r1 / 2026-09-29 |
| Parent TASKS | [DEMO](#document-19) |
| Executor / collaborators | Unassigned example |
| Requested outcome and instruction/source | Demonstrate document structure using SOURCE-01 and SOURCE-02 |
| Included scope / exclusions | Label validation/normalization; no models, roles, storage or external services |
| PRD clause and architecture references | Inline DEMO SOURCE-01/02 r1; Validate and Normalize nodes |
| Working checkout / branch / base | NOT_STARTED |
| Affected paths | Hypothetical provider and test paths; PENDING_DESIGN until instantiated |

<a id="document-20-heading-2"></a>

#### 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | ../specs/DEMO-001-label/ relative to this file | This task only |
| spec.md | [spec](#document-22) | ACs |
| plan.md | [plan](#document-23) | Blocks/checks |
| tasks.md | [tasks](#document-24) | Work/evidence |
| evidence/ | ../specs/DEMO-001-label/evidence/ when executed | Actual runs |
| Supporting artifacts | None | N/A |

<a id="document-20-heading-3"></a>

#### 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| DEMO-SYSTEM/T001 | Actual consumer wiring | Needed for provider-consumer boundary execution, not block implementation | DEMO-001/V03 and T004 |

<a id="document-20-heading-4"></a>

#### 4. Embedded cross-module agreements
<a id="document-20-heading-5"></a>

##### IF-001 at r1
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | DEMO-001 -> DEMO-SYSTEM |
| Purpose / source requirement | SOURCE-01/02 result consumed by SOURCE-03 display |
| Inputs | label: unknown value; valid only if string with nonempty trimmed content |
| Outputs | Success: status=ok and normalized_label string; invalid: status=error and code=INVALID_LABEL, with no normalized_label |
| States and invariants | Stateless; no partial success on invalid input |
| Errors, timeout, retry, cancellation | INVALID_LABEL is a normal error result; no retries; timeout/cancellation N/A for this synchronous in-process toy |
| Side effects and idempotency | No side effects; same input gives same result |
| Compatibility and migration | r1 initial agreement; any field/semantic change updates consumers and invalidates V03/system evidence |
| Machine-readable schema / source path | None; hypothetical implementation has not been created |
| Provider/consumer verification responsibilities | DEMO-001/V01,V02 verify provider; V03 connects actual consumer; DEMO-SYSTEM/V01,V02 verify full journeys |
| Open agreement questions | None within the fictional scope |

Consumed agreements: None.

<a id="document-20-heading-6"></a>

#### 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 / 2026-09-29 | Implementation paths not bound | Plan/work items | All execution NOT_RUN | Unassigned; bind only if example is implemented |

---

<a id="document-21"></a>

## 21. TASK: DEMO-SYSTEM - Verify the complete label journey

Source: [docs/code/code_sop/examples/DEMO/DEMO-SYSTEM/TASK.md](code_sop/examples/DEMO/DEMO-SYSTEM/TASK.md)

<a id="document-21-heading-0"></a>

### TASK: DEMO-SYSTEM - Verify the complete label journey
Fictional example; no system has been executed.

<a id="document-21-heading-1"></a>

#### 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | DEMO-SYSTEM / r1 / 2026-09-29 |
| Parent TASKS | [DEMO](#document-19) |
| Executor / collaborators | Unassigned example |
| Requested outcome and instruction/source | Demonstrate consumer integration and system verification of SOURCE-03 |
| Included scope / exclusions | Request-to-display journey; no model services or persistence |
| PRD clause and architecture references | Inline DEMO SOURCE-03 r1; provider-to-display edge |
| Working checkout / branch / base | NOT_STARTED |
| Affected paths | Hypothetical consumer/entry point/system tests; PENDING_DESIGN |

<a id="document-21-heading-2"></a>

#### 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | ../specs/DEMO-SYSTEM-journey/ relative to this file | This task only |
| spec.md | [spec](#document-25) | System ACs |
| plan.md | [plan](#document-26) | Candidate/journeys |
| tasks.md | [tasks](#document-27) | Work/evidence |
| evidence/ | ../specs/DEMO-SYSTEM-journey/evidence/ when executed | Actual runs |
| Supporting artifacts | None | N/A |

<a id="document-21-heading-3"></a>

#### 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| DEMO-001/B01,B02 and IF-001@r1 | Provider and interface definition | Definition needed for wiring; working blocks needed for integration | T001,T002 |
| DEMO-001/V03 | Connected boundary evidence | Needed before final system acceptance; does not block initial wiring | T003,T004 |

<a id="document-21-heading-4"></a>

#### 4. Embedded cross-module agreements
Owned: None; this task consumes an existing boundary and adds no new cross-task interface.
Consumed: [DEMO-001 IF-001@r1](#document-20-heading-4). Do not copy its fields here.

<a id="document-21-heading-5"></a>

#### 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 / 2026-09-29 | No executable system candidate | All | All results NOT_RUN | Unassigned; bind actual implementation before execution |

---

<a id="document-22"></a>

## 22. Feature Specification: DEMO-001 - Label normalization

Source: [docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/spec.md](code_sop/examples/DEMO/specs/DEMO-001-label/spec.md)

<a id="document-22-heading-0"></a>

### Feature Specification: DEMO-001 - Label normalization
**TASK**: [DEMO-001](#document-20)
**Parent TASKS**: [DEMO](#document-19)
**Revision / date**: r1 / 2026-09-29
**Feature Branch**: NOT_STARTED
**Input**: DEMO inline SOURCE-01/02 r1
**Status**: Specified for illustration only

<a id="document-22-heading-1"></a>

#### User Scenarios & Testing
<a id="document-22-heading-2"></a>

##### User Story 1 - Normalize an executor label (Priority: P1)
An executor supplies a label; the provider returns normalized text or a defined invalid-input result.
**Independent Test**: supply "  ALPHA  " and expect normalized text "alpha"; supply whitespace or a number and expect INVALID_LABEL.
**Acceptance Scenarios**:
1. Given a valid string, when processed, then trim surrounding whitespace and lowercase the content.
2. Given invalid input, when processed, then return the defined error with no success field.

<a id="document-22-heading-3"></a>

##### Edge Cases
Empty string, whitespace-only string and non-string input are invalid. Already-normalized text is unchanged. Persistence, concurrency and external network recovery are N/A for the stateless fictional scope.

<a id="document-22-heading-4"></a>

#### Requirements
<a id="document-22-heading-5"></a>

##### Functional Requirements
- FR-001: validate according to SOURCE-01.
- FR-002: transform valid strings according to SOURCE-02.
<a id="document-22-heading-6"></a>

##### Key Entities
Executor label; see TASK IF-001@r1 for interface semantics.

<a id="document-22-heading-7"></a>

#### Success Criteria
<a id="document-22-heading-8"></a>

##### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | SOURCE-01 / FR-001 / US1 | Invalid inputs return INVALID_LABEL and no normalized_label | BLOCK, BOUNDARY |
| AC-002 | SOURCE-02 / FR-002 / US1 | Valid strings return exactly their trimmed lowercase content | BLOCK, BOUNDARY |

<a id="document-22-heading-9"></a>

#### Scope and Assumptions
Only the fictional source is authoritative for this example. No models or role-based inputs are involved. System display behavior is owned by DEMO-SYSTEM, not duplicated here. The implementation is absent and all runtime claims remain unverified.

---

<a id="document-23"></a>

## 23. Implementation Plan: DEMO-001

Source: [docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/plan.md](code_sop/examples/DEMO/specs/DEMO-001-label/plan.md)

<a id="document-23-heading-0"></a>

### Implementation Plan: DEMO-001
**TASK**: [DEMO-001](#document-20) | **Spec**: [r1](#document-22)
**Revision / date**: r1 / 2026-09-29 | **Branch**: NOT_STARTED
**Input sources**: DEMO inline source/architecture r1

<a id="document-23-heading-1"></a>

#### Summary
Validate the value, normalize valid text and return the TASK-defined result. This is a plan example, not an implementation.

<a id="document-23-heading-2"></a>

#### Technical Context
Runtime and actual source/test paths are PENDING_DESIGN if this example is selected for implementation. No external service, storage or model is required. Manual procedures below describe observable behavior without assuming a test runner.

<a id="document-23-heading-3"></a>

#### Constitution Check
One TASK/feature; ACs in spec; IF in TASK; work and evidence in tasks. Runtime evidence is NOT_RUN and no approval cards are used.

<a id="document-23-heading-4"></a>

#### Project Structure
Hypothetical provider entry point and tests are not created. Bind their actual paths before executing T001. Native documents live in this example directory.

<a id="document-23-heading-5"></a>

#### Blocks and Dependencies
| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Validate / AC-001 | Unknown input -> valid text or error; no side effects | IF-001@r1 | PENDING_DESIGN provider |
| B02 | Normalize / AC-002 | Valid text -> normalized result | B01 and IF-001@r1 | PENDING_DESIGN provider |

Order: B01 -> B02. V03 additionally requires DEMO-SYSTEM consumer wiring, not completed system acceptance.

<a id="document-23-heading-6"></a>

#### Interfaces and Technical Decisions
[IF-001@r1](#document-20-heading-4) is canonical. A stateless synchronous function is sufficient for this fictional behavior; no storage or retry mechanism is needed.

<a id="document-23-heading-7"></a>

#### Verification Design
| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BLOCK | B01 / AC-001 | "", "   ", 42; local real provider | Error and no success field per AC-001 | Invoke provider for each value; capture complete returned fields | Executable provider; raw input/output records |
| V02 | BLOCK | B02 / AC-002 | "  ALPHA  ", "alpha"; local real provider | Exactly "alpha" per AC-002 | Invoke provider for both values and compare exact output | Executable provider; raw records |
| V03 | BOUNDARY | IF-001@r1 / AC-001, AC-002 | "  ALPHA  ", then " "; real provider and consumer | Consumer reads success/error fields without stale success | Send both values across actual boundary; capture result object and consumer state | DEMO-SYSTEM/T001; boundary trace and source hashes |

<a id="document-23-heading-8"></a>

#### System Candidate and Journeys
DEMO-SYSTEM records the combined provider/consumer candidate and verifies request-to-display behavior. Reuse block evidence only when candidate comparison establishes unchanged relevant inputs.

<a id="document-23-heading-9"></a>

#### Unresolved Decisions and Impact
No executable paths/runtime are bound. All runtime checks remain NOT_RUN. IF or provider changes invalidate V03 and affected system checks.

---

<a id="document-24"></a>

## 24. Tasks: DEMO-001

Source: [docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/tasks.md](code_sop/examples/DEMO/specs/DEMO-001-label/tasks.md)

<a id="document-24-heading-0"></a>

### Tasks: DEMO-001
**TASK**: [DEMO-001](#document-20) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/

<a id="document-24-heading-1"></a>

#### Work Items
<a id="document-24-heading-2"></a>

##### Foundation / shared definitions
- [ ] T001 [US1] Bind real provider and test paths/runtime in plan.md if implementation is requested.
<a id="document-24-heading-3"></a>

##### Block B01 and B02
- [ ] T002 [US1] Implement B01/B02 according to AC-001/002 at the paths established by T001.
- [ ] T003 [US1] Execute V01/V02 and store actual run records in evidence/.
<a id="document-24-heading-4"></a>

##### Connected boundaries
- [ ] T004 [US1] After DEMO-SYSTEM/T001, execute V03 and store actual boundary evidence in evidence/.
<a id="document-24-heading-5"></a>

##### System contribution
- [ ] T005 [US1] Supply provider candidate identity and current evidence to DEMO-SYSTEM's native matrix.

<a id="document-24-heading-6"></a>

#### Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](#document-22) | B01 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | Fictional example |
| [AC-001](#document-22) | IF-001@r1 | T002 | V03 / T004 | NOT_RUN | None / NOT_BUILT | Needs consumer wiring |
| [AC-002](#document-22) | B02 | T002 | V02 / T003 | NOT_RUN | None / NOT_BUILT | Fictional example |
| [AC-002](#document-22) | IF-001@r1 | T002 | V03 / T004 | NOT_RUN | None / NOT_BUILT | Needs consumer wiring |

<a id="document-24-heading-7"></a>

#### Dependency Order and Execution Notes
T001 -> T002 -> T003; V03 requires consumer wiring; final system acceptance follows boundary verification. Do not execute this toy scope without an implementation request.

<a id="document-24-heading-8"></a>

#### Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No.
- Required AC/check coverage: 2 ACs, 3 V IDs, all NOT_RUN.
- Conclusion: NOT_READY.
- Remaining limitations: no executable implementation.

<a id="document-24-heading-9"></a>

#### Evidence Invalidation
No existing runtime evidence. A future interface change must invalidate boundary and downstream system results.

---

<a id="document-25"></a>

## 25. Feature Specification: DEMO-SYSTEM

Source: [docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/spec.md](code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/spec.md)

<a id="document-25-heading-0"></a>

### Feature Specification: DEMO-SYSTEM
**TASK**: [DEMO-SYSTEM](#document-21)
**Parent TASKS**: [DEMO](#document-19)
**Revision / date**: r1 / 2026-09-29
**Feature Branch**: NOT_STARTED
**Input**: DEMO SOURCE-03 r1
**Status**: Specified for illustration

<a id="document-25-heading-1"></a>

#### User Scenarios & Testing
<a id="document-25-heading-2"></a>

##### User Story 1 - See a complete request result (Priority: P1)
A request traverses the real provider and consumer to display the result.
**Independent Test**: submit "  ALPHA  ", then invalid whitespace; observe the visible result for each.
**Acceptance Scenarios**:
1. Valid request displays "alpha".
2. Invalid request displays INVALID_LABEL and clears the previous success value.

<a id="document-25-heading-3"></a>

##### Edge Cases
Success followed by failure must not retain stale success. Persistence and external outages are excluded by this toy source.

<a id="document-25-heading-4"></a>

#### Requirements
<a id="document-25-heading-5"></a>

##### Functional Requirements
- FR-001: display the provider's successful normalized value.
- FR-002: display the defined error and remove stale success on invalid input.
<a id="document-25-heading-6"></a>

##### Key Entities
Request, provider result and consumer display state; consume IF-001@r1.

<a id="document-25-heading-7"></a>

#### Success Criteria
<a id="document-25-heading-8"></a>

##### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | SOURCE-03 / FR-001 / US1 | Real complete journey displays "alpha" for "  ALPHA  " | SYSTEM |
| AC-002 | SOURCE-03 / FR-002 / US1 | A subsequent whitespace request displays INVALID_LABEL and no prior success | SYSTEM |

<a id="document-25-heading-9"></a>

#### Scope and Assumptions
Participating behavior: DEMO-001/AC-001 and AC-002. Their block criteria are not duplicated. No model service is involved. All outcomes above are expectations, not observed passes.

---

<a id="document-26"></a>

## 26. Implementation Plan: DEMO-SYSTEM

Source: [docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/plan.md](code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/plan.md)

<a id="document-26-heading-0"></a>

### Implementation Plan: DEMO-SYSTEM
**TASK**: [DEMO-SYSTEM](#document-21) | **Spec**: [r1](#document-25)
**Revision / date**: r1 / 2026-09-29 | **Branch**: NOT_STARTED
**Input sources**: DEMO SOURCE-03 and architecture r1

<a id="document-26-heading-1"></a>

#### Summary
Wire an actual consumer to the provider, establish a candidate and verify complete request-to-display behavior.

<a id="document-26-heading-2"></a>

#### Technical Context
Runtime and executable paths are PENDING_DESIGN. All connections are local real implementations; no stub can establish final system acceptance.

<a id="document-26-heading-3"></a>

#### Constitution Check
Owns only system ACs. References provider agreement/evidence and maintains its own native work matrix. No separate review or closure card.

<a id="document-26-heading-4"></a>

#### Project Structure
Consumer entry point, display and system checks are hypothetical and not created. Bind paths before T001 execution.

<a id="document-26-heading-5"></a>

#### Blocks and Dependencies
| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Consumer/display / AC-001, AC-002 | Request -> visible result; no stale success | DEMO-001/B01,B02 and IF-001@r1 | PENDING_DESIGN consumer |
| B02 | Complete journey verification / AC-001, AC-002 | Exact candidate and request -> observed journey evidence | B01, provider block evidence and DEMO-001/V03 | PENDING_DESIGN system checks |

<a id="document-26-heading-6"></a>

#### Interfaces and Technical Decisions
Consume [IF-001@r1](#document-20-heading-4). Display state is reset on errors. No independent copy of the interface schema.

<a id="document-26-heading-7"></a>

#### Verification Design
| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | SYSTEM | B01,B02 / AC-001 / DEMO-001 blocks / IF-001 | "  ALPHA  "; all local real components | Display exactly "alpha" per AC-001 | Launch candidate entry; submit fixture; capture request, provider result and display | Candidate hashes, valid block/boundary evidence, trace |
| V02 | SYSTEM | B01,B02 / AC-002 / IF-001 | Same session after V01, then " " | Display INVALID_LABEL with no stale "alpha" per AC-002 | Submit invalid fixture and capture error plus resulting display state | Same candidate and session; trace |

<a id="document-26-heading-8"></a>

#### System Candidate and Journeys
The run record must contain actual provider, consumer, check and configuration hashes, runtime and starting state. Candidate is currently NOT_BUILT. Final runs require DEMO-001/V01,V02,V03 valid for that candidate. Earlier exploratory runs cannot establish final completion.

<a id="document-26-heading-9"></a>

#### Unresolved Decisions and Impact
No actual runtime/paths exist. Provider, consumer or interface changes require impact assessment and affected system re-execution.

---

<a id="document-27"></a>

## 27. Tasks: DEMO-SYSTEM

Source: [docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/tasks.md](code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/tasks.md)

<a id="document-27-heading-0"></a>

### Tasks: DEMO-SYSTEM
**TASK**: [DEMO-SYSTEM](#document-21) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/

<a id="document-27-heading-1"></a>

#### Work Items
<a id="document-27-heading-2"></a>

##### Consumer block and integration
- [ ] T001 [US1] Bind paths and implement actual consumer wiring for B01; update plan.md with executable entries.
- [ ] T002 [US1] Assemble provider/consumer/check/configuration candidate and capture its identity; obtain DEMO-001/V03 boundary evidence.
<a id="document-27-heading-3"></a>

##### Whole-system verification
- [ ] T003 [US1] Execute V01 on the candidate and retain the actual run in evidence/.
- [ ] T004 [US1] Execute V02 in the same candidate session and retain the actual run in evidence/.

<a id="document-27-heading-4"></a>

#### Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](#document-25) | B01,B02; DEMO-001/B01,B02; IF-001@r1 | T001,T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | Fictional example |
| [AC-002](#document-25) | B01,B02; IF-001@r1 | T001,T002 | V02 / T004 | NOT_RUN | None / NOT_BUILT | Requires same candidate/session |

<a id="document-27-heading-5"></a>

#### Dependency Order and Execution Notes
Consumer wiring can follow the IF definition. Final system checks follow valid provider block and boundary evidence. V02 follows V01 in the same session to expose stale-state defects.

<a id="document-27-heading-6"></a>

#### Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No.
- Required AC/check coverage: 2 system ACs and 2 system V IDs, all NOT_RUN.
- Conclusion: NOT_READY.
- Remaining limitations: no implementation or runtime evidence.

<a id="document-27-heading-7"></a>

#### Evidence Invalidation
No existing evidence. A candidate change invalidates relevant system conclusions until impact assessment and required reruns.

---

<a id="document-28"></a>

## 28. Complete documentation catalog - SOP v2

Source: [docs/code/code_sop/README.md](code_sop/README.md)

<a id="document-28-heading-0"></a>

### Complete documentation catalog - SOP v2
The package has English and Chinese entry guides. Editable process, template and example sources remain English; a complete Chinese handbook is also provided. Start with [Code SOP](#document-1). This catalog is the complete process package; optional generated research/schema files are not additional mandatory cards.

<a id="document-28-heading-1"></a>

#### Reading order
1. [Package entry](#document-3)
2. [Code SOP](#document-1)
3. [Spec Kit workflow](#document-10)
4. [Block-to-system verification](#document-2)
5. [Worked example](#document-18)
6. [Future M1 register](#document-17)

<a id="document-28-heading-2"></a>

#### Guides and instructions
| Document | Purpose |
| --- | --- |
| [Git workflow](#document-11) | Branch/candidate handling without automatic commits |
| [Migration and preparation](#document-12) | Replacement map and treatment of unfinished historical work |
| [Root AGENTS template](#document-13) | Reusable durable repository instructions |
| [Local AGENTS template](#document-14) | Reusable subtree context |
| [Active repository AGENTS](#document-15) | Deployed v2 repository entry and rules |
| [Active constitution](#document-16) | Spec Kit's v2 principles |

<a id="document-28-heading-3"></a>

#### Required record templates
| Template | Destination / authority |
| --- | --- |
| [TASKS](#document-4) | docs/tasks/PROGRAM-ID/TASKS.md; whole-program source/coverage/dependencies |
| [TASK](#document-5) | docs/tasks/PROGRAM-ID/TASK-ID/TASK.md; identity and embedded agreements |
| [Evidence](#document-6) | Selected feature evidence/RUN-ID.md; actual run observations |

These are the only record templates in the active package. Evidence is an output attachment, not an extra task card.

<a id="document-28-heading-4"></a>

#### Native Spec Kit templates
| Native template | Destination / authority |
| --- | --- |
| [Spec override](#document-7) | Feature spec.md; requirements and ACs |
| [Plan override](#document-8) | Feature plan.md; design, blocks and checks |
| [Tasks override](#document-9) | Feature tasks.md; work and AC-to-evidence matrix |

Overrides are canonical. Do not maintain duplicate copies under this catalog's templates directory.

<a id="document-28-heading-5"></a>

#### Complete fictional example
| Document | Link |
| --- | --- |
| Program register and inline source | [DEMO TASKS](#document-19) |
| Provider TASK | [DEMO-001](#document-20) |
| Provider native artifacts | [spec](#document-22), [plan](#document-23), [tasks](#document-24) |
| System TASK | [DEMO-SYSTEM](#document-21) |
| System native artifacts | [spec](#document-25), [plan](#document-26), [tasks](#document-27) |

No example runtime result is reported as passed. Actual future runs use the evidence template.

<a id="document-28-heading-6"></a>

#### Delivery
The complete bundle is generated from this package, the active root instructions, constitution, native overrides and future-M1 register. Delivery includes a file manifest and documentation-check record. The repository's older CODEX_DEMO.md describes historical feature work and is not part of this process package.

The previous kickoff ZIP and obsolete authorization/review/checklist/testing templates are removed to prevent accidental reuse.

Download the [complete ZIP](AI4Research_Documentation_v2.zip), read the [English handbook](AI4Research_Documentation_v2.md) or [Chinese handbook](AI4Research_Documentation_v2.zh-CN.md), or inspect the [manifest](DELIVERY_MANIFEST.json) and [documentation checks](#document-29). These are generated delivery snapshots; edit the source files listed above.

---

<a id="document-29"></a>

## 29. Documentation verification record

Source: [docs/code/DOCUMENTATION_CHECKS.md](DOCUMENTATION_CHECKS.md)

<a id="document-29-heading-0"></a>

### Documentation verification record
Date: 2026-09-29. Scope: SOP v2 documentation, not application/runtime acceptance.

<a id="document-29-heading-1"></a>

#### Checks performed
| Check | Observed result |
| --- | --- |
| Initial source-document scan | 32 English source documents; no empty files or CJK text |
| Initial local-link/anchor scan | 99 references checked, zero failures before adding delivery links |
| TASK and native work-list sections | Required example sections present; no checked example work items |
| Example AC/check correspondence | DEMO-001: 2 ACs, 3 checks, 5 work items; DEMO-SYSTEM: 2 ACs, 2 checks, 4 work items; all mapped |
| Active record template inventory | Exactly TASKS, TASK and EVIDENCE templates |
| Native resolver | spec-template, plan-template and tasks-template all resolve to project overrides |
| Removed workflow-reference scan | No active references to removed template filenames or former independent-review requirement |
| Whitespace/error check | git diff --check passed |
| Change scope | Only docs/code, future-M1 skeleton, root AGENTS, constitution and native overrides changed |
| Final source/handbook link scan | 34 Markdown files, 247 local links/anchors, zero failures |
| Delivery archive | 35 entries; archive integrity and manifest SHA256 checks passed |
| Commit state | HEAD remained 918df5e4081ed35d53257dfccd33119a7b639c57; no commit operation performed |

<a id="document-29-heading-2"></a>

#### Method and environment
Checks ran from D:\research\ai_for_research\jiuwenswarm using Python 3.13.1, PowerShell and Git.
- Python inspected UTF-8 contents, resolved relative Markdown links/heading anchors, compared example AC/V/work-item sets, checked expected template names and checked changed paths.
- PowerShell loaded .specify/scripts/powershell/common.ps1 and called Resolve-Template and Resolve-TemplateContent for each native template, confirming override paths and nonempty content.
- Git supplied whitespace diagnostics, changed-path inventory and candidate HEAD.

The final bundle is additionally checked for archive integrity, manifest/content agreement and delivery links after generation. The delivery manifest provides source and snapshot content hashes.

<a id="document-29-heading-3"></a>

#### Scope limits
No M1 runtime suite, external model invocation, tool upgrade, commit, push or deployment was performed. Fictional example runtime checks remain NOT_RUN. Future master PRD and architecture remain PENDING_SOURCE. Existing historical tasks and application tests were not rewritten.

<a id="document-29-heading-4"></a>

#### Entry-guide localization
The package entry docs/code/README.md is now Chinese at the user's request. Other guides, templates and examples remain English. The handbook, manifest and ZIP are regenerated to include that entry. Earlier English-only scan results describe the initial delivery before this localization.

<a id="document-29-heading-5"></a>

#### Complete bilingual delivery
2026-09-30: added an English-only README.en.md and used it as the English handbook entry. Chinese README.md accompanies the complete Chinese handbook. Counts above are historical results for the prior delivery; coverage, sections/tables, work-item IDs, links, language and archive hashes are checked again for this delivery. Translations are stored by source path in translations.zh-CN.json for regeneration and comparison. No commit was created.

Current delivery results: all 33 bilingual sections correspond; heading counts, table structure, work-item IDs and code blocks match. The English handbook contains no CJK prose. Each handbook has 172 valid links. The ZIP has 38 entries with matching manifest hashes.

<a id="document-29-heading-6"></a>

#### Module-guide removal and task-file clarification
2026-09-30: removed the four legacy RSI, Router, Capsule and Verifier module guides at the user's request. Removed their catalog entries and translations, and regenerated both handbooks and the ZIP. Clarified that a logical TASK owns its spec.md, plan.md and tasks.md, while TASK.md is their entry and link registry. The current handbooks each contain 29 sections; previous counts above describe earlier deliveries. No commit was performed for this update.
