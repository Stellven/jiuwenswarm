# AI4Research Code SOP v2
Revision: 2026-10-05 (tool packaging and directory layout). Current source readiness is recorded in the registered TASKS/TASK/native artifacts.

## 1. Hierarchy
**TASKS -> TASK -> one Spec Kit feature directory per TASK.**

- TASKS is the program register: source baselines, requirement allocation, task graph, interface index and system verification.
- TASK is the task's identity and entry point: executor, scope, exact native artifact paths, dependencies and embedded cross-module agreements.
- Spec Kit is the working core: spec.md defines acceptance; plan.md defines technical design and verification procedures; tasks.md holds ordered work, progress and the acceptance-to-evidence matrix.
- Evidence records actual verification results inside that feature directory. It is not another task list.

Uppercase TASKS.md is the program register. Lowercase tasks.md is one task's native work list. Install the Spec Kit Codex plugin once and retain project-owned rules per checkout; each TASK gets its own feature directory, not a separate tool installation.

A TASK is the logical task unit; TASK.md is its entry file. The task's functional specification (spec.md), implementation plan (plan.md), work list (tasks.md) and evidence belong to that TASK, but are separate files in its registered Spec Kit directory. TASK.md links to them; their full contents are not embedded in TASK.md.

There is no separate coding-authorization card, implementation checklist, test-report card, review card, handoff card, change-request card, or Manual design/plan track. Record the user's requested scope directly in TASK. This workflow introduces no reviewer-assignment or approval stage. Existing platform permissions and explicit user instructions still apply to actual external actions.

## 2. Single authorities
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

## 3. Paths and IDs
Recommended repository layout:
```text
docs/code/Missions/M1/TASKS.md
docs/code/Missions/M1/M1-001/TASK.md
docs/code/Missions/M1/M1-SYSTEM/TASK.md
specs/M1-001-slug/{spec.md,plan.md,tasks.md,evidence/}
specs/M1-SYSTEM-slug/{spec.md,plan.md,tasks.md,evidence/}
```
Use qualified IDs: M1-001/AC-001, M1-001/B01, M1-001/V01 and M1-001/T001. Interface IDs are program-wide, such as M1-IF-001@r1. Never reuse retired IDs.

Each TASK has an accountable executor; collaborators may be named. There is no role taxonomy. A task may span modules, and a module may need several tasks. Split by bounded, verifiable behavior and dependencies.

## 4. Preparation before final inputs
Build the document skeleton now. Missing future PRD, architecture, model lists, budgets or thresholds use PENDING_SOURCE, identifying affected work and a resolution condition. They are ordinary preparation states, not a requirement to complete existing teammates' work or run a pilot.

When inputs arrive:
1. Register actual paths, versions, content hashes and sizes.
2. Give source clauses and architecture nodes stable IDs or exact section locators.
3. Allocate every in-scope clause to TASKs and ACs; record exclusions with reasons.
4. Establish dependencies and embed agreements in their owning TASKs.
5. Populate each task's spec, plan, work items and evidence matrix before dependent implementation.
6. Verify the full M1 through the system TASK on an integrated candidate.

Do not fabricate a real task breakdown from absent requirements. The worked example is illustrative. Existing task records remain historical evidence and do not gate this preparation.

## 5. Working loop
1. Locate TASK through TASKS and read its native artifacts and dependencies.
2. Specify observable ACs, failure behavior and applicable nonfunctional thresholds.
3. Plan implementation blocks, affected files, agreements, fixtures and verification methods.
4. Generate native work items and the correspondence matrix. Every AC maps to implementation and verification; every required check has an independent expected outcome.
5. Implement and verify block by block. Preserve evidence, repair failures and follow the dependency graph. Independent blocks can proceed while another is blocked.
6. Connect blocks and verify real provider/consumer boundaries.
7. Verify complete M1 journeys and system constraints through the system TASK.
8. Update the same native records; derive program progress from them.

This is a development loop, not a sequence of approval cards. AI analysis helps detect inconsistencies; runtime evidence establishes behavior.

## 6. Cross-module agreements inside TASK
One TASK owns each interface definition. Its interface section identifies provider and consumer TASKs; input/output structure and semantics; validation; error states; timeout, retry and cancellation; side effects and idempotency; compatibility; and boundary verification. Explain N/A values.

Consumers reference the owner and revision. Avoid parallel definitions. Separate interface-definition dependencies from implementation dependencies to expose and resolve cycles.

Record interface changes in the owning TASK change table, update affected consumers, and invalidate affected evidence. Unknown details block only dependent work.

## 7. Verification and completion
Follow [VERIFICATION.md](VERIFICATION.md).
- A checked work item means work was done, not that acceptance passed.
- An AC passes only when all mapped required checks have valid PASS evidence.
- A TASK completes when required work, ACs and boundaries pass and no unresolved dependency invalidates the result.
- M1 completes when source allocation is complete, required tasks are verified against the candidate, and its system TASK passes on that same candidate.
- NOT_RUN, BLOCKED, FAIL and STALE are not PASS. Exclusions require a recorded scope basis; they cannot erase a failure.

Completion is based on evidence, without a separate review-and-close stage.

## 8. Large inputs, changes and continuity
Retain the complete 100-200 KB source, but give each feature its relevant clauses, architecture nodes, agreements and surrounding constraints. Do not use summaries as substitutes for source coverage. TASKS detects gaps across the slices.

Use stable locators and revisions so work can resume after a session restart. Maintain an architecture overview and readable module/interaction views linked by node IDs. A diagram alone does not specify interface semantics.

When requirements change, update the baseline and allocation, affected agreements and native artifacts. Record affected AC/block/check IDs and mark their evidence STALE. Ordinary progress changes only tasks.md. Keep previous runs and point to the current effective evidence.

Integrate dependent blocks early. Whole-system acceptance covers the entire M1; smaller implementation units do not reduce that scope.

## 9. Templates and tools
Follow the tables in the [catalog](CATALOG.md). Preserve required fields, use meaningful N/A explanations and record unresolved conditions.

TASK-native templates live in the plugin, alongside TASKS/TASK templates. Project-specific overrides may live in .specify/templates/overrides/. Read [Spec Kit workflow](SPEC_KIT_WORKFLOW.md) and [Git workflow](GIT_WORKFLOW.md). Generated commands never override an explicit no-commit instruction.
