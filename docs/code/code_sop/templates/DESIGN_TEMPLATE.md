# [TASK-ID] — [Design title]

> Suggested location: `docs/design/<TASK-ID>.md`  
> Maintainer: task author. Approver: Code Lead.  
> After copying: fill in all placeholders and remove template guidance that no longer applies. Preserve actual approval, revision, and evidence records. This template is not approval.

## Usage rules

- Use a full design for new behavior, changes across modules, public interfaces, algorithms or data flows, and significant performance objectives.
- For a local, low-risk change that does not alter architecture or contracts, keep a minimum design in `docs/tasks/<TASK-ID>/TASK.md` and `write_code.md`: problem, proposed behavior, file scope, acceptance criteria, and Code Lead approval. A separate design file is optional; approval before implementation remains mandatory.
- Complete required fields. For a conditional field, use `N/A — [specific reason]`. For unresolved questions, record the owner and resolution condition; do not disguise them as N/A.
- Revise and approve material changes to scope, behavior, contracts, or acceptance criteria before implementing the affected work. Do not request approval again when an existing decision already covers the same scope.

## 1. Design control — required

| Field | Record |
| --- | --- |
| TASK-ID | [Fill in task identifier] |
| Author / module owner / Code Lead | [Fill in names or accounts] |
| Design version | [Fill in v1, v2, or the project version scheme] |
| Design status | Draft / Pending approval / Approved / Superseded; initially Draft |
| Code baseline | `huawei_waterloo_main_branch` at [full commit SHA] |
| Task definition and requirements version | `docs/tasks/<TASK-ID>/TASK.md` at [version] |
| Implementation directive | `docs/tasks/<TASK-ID>/write_code.md` |
| Implementation plan | `docs/exec-plans/<TASK-ID>.md`; for a simplified task, identify the actual brief-plan section in TASK |
| Related architecture / contracts / ADRs | [Fill in repository-relative paths and versions, or explain why none apply] |

## 2. Problem and scope — required

- Current behavior and evidence: [Fill in a reproducible problem, requirement source, or evidence of the current state].
- Target behavior: [Who observes what outcome, under which conditions].
- In scope: [Capabilities, modules, and scenarios covered].
- Out of scope: [Explicit exclusions].
- Known constraints: [Compatibility, environment, time, or resource constraints; state none if applicable].

## 3. Acceptance-to-design mapping — required

Acceptance criteria and thresholds are maintained only in the acceptance section of `docs/tasks/<TASK-ID>/TASK.md`, requirements version [fill in]. Reference its stable AC identifiers here. This table explains design and verification coverage; it does not define separate thresholds. Revise TASK and obtain the appropriate approval before changing a criterion, then update this mapping.

| TASK acceptance ID / section | Design mechanism / section | Verification method / test location | Relevant boundaries and failure paths |
| --- | --- | --- | --- |
| AC-01 / [actual TASK section] | [How the design satisfies the criterion] | [Test, inspection, or evaluation] | [Relevant edge cases] |

For performance or research evaluation, describe the measurement protocol: baseline version, dataset version or digest, seeds or repetition count, hardware, and environment. Reference the metrics and thresholds in the specified TASK version. Record measured results only in the test report or TASK verification section; unmeasured behavior is not verified.

## 4. Proposed approach — required

1. Entry points and preconditions: [Callers, triggers, and existing data].
2. Main flow: [Ordered processing steps, state changes, and outputs].
3. Failure paths: [How errors propagate, recover, or terminate].
4. Invariants: [Rules every valid implementation must preserve].

### Affected boundaries

| Component / module | Proposed change | Provided / consumed interface | Affected callers | Owner |
| --- | --- | --- | --- | --- |
| [Verified module name] | [Behavior or responsibility change] | [Contract path or symbol] | [Module or external consumer] | [Name] |

Names such as RSI, Router, Capsule, and Verifier identify modules whose responsibilities require confirmation. Derive paths, responsibilities, and interactions from project evidence, never from their names. Use [ARCHITECTURE_TEMPLATE.md](ARCHITECTURE_TEMPLATE.md) and [CONTRACT_TEMPLATE.md](CONTRACT_TEMPLATE.md) when applicable.

### Files and dependencies — required

| File / directory | Add / modify / delete | Responsibility and proposed change | Dependencies / callers | Related AC |
| --- | --- | --- | --- | --- |
| [Actual path; label proposed new files] | [Change type] | [Purpose and change] | [Paths or symbols] | AC-01 |

Update actual file and function changes in `docs/code-map/FILE_MAP.md` using [FILE_MAP_TEMPLATE.md](FILE_MAP_TEMPLATE.md).

## 5. Contracts, compatibility, and data — conditional

- Interface changes: [Changes to inputs, outputs, errors, or invariants; explicitly state when unchanged].
- Compatibility strategy: [Consumer migration, version coexistence, and defaults; explain N/A].
- Data or state changes: [Formats, storage locations, migration, and recovery].
- Security or privacy boundaries: [Relevant permissions, sensitive data, and credential handling; explain when unaffected].

## 6. Alternatives and risks — required, scale to complexity

| Alternative | Main benefits | Costs / constraints | Reason selected or rejected |
| --- | --- | --- | --- |
| [Approach] | [Benefits] | [Costs] | [Reason] |

A simple change may explain the choice in one sentence. Record decisions with lasting architectural, dependency, or public-protocol consequences in an ADR using [ADR_TEMPLATE.md](ADR_TEMPLATE.md).

| Risk / unresolved question | Impact | Resolution or mitigation | Owner | Condition for starting affected implementation |
| --- | --- | --- | --- | --- |
| [Risk or question; state none if applicable] | [Impact] | [Verification or mitigation] | [Name] | [Resolution or explicit risk-acceptance evidence] |

## 7. Verification and delivery plan — required

- Checks mapped to AC identifiers: [Test categories, targets, and command sources].
- Dependencies and integration boundaries to verify: [Callers and verification method].
- Rollback or recovery: [How behavior or data can be restored; explain N/A when there is no runtime impact].
- Documents to update: [Actual architecture, contract, file-map, or module AGENTS paths].
- Completion evidence: [Actual test report or TASK/PR verification section], [task `review.md`], and [actual HANDOFF or TASK/PR handoff section]. Do not retain references to files that were not created.

## 8. Approval record — required

Approval requires a traceable, explicit Code Lead decision. AI drafts, author claims, blank signatures, and checkboxes do not constitute approval.

| Design version | Code baseline SHA | Code Lead | Decision | Time and timezone | Evidence location / exact decision | Conditions |
| --- | --- | --- | --- | --- | --- | --- |
| [Version] | [SHA] | [Name] | Pending approval | [Actual time or pending] | [Explicit approval in a PR, issue, or project record; otherwise pending] | [Conditions or none] |

## 9. Revision history — when revised

| Date | Version | Change and reason | Effect on existing approval | Follow-up |
| --- | --- | --- | --- | --- |
| [Date] | [Version] | [Change] | [Yes/no and reason] | [New approval or record update] |

