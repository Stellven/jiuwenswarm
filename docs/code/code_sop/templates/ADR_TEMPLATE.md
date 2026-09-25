# ADR-[NNNN]: [Decision title]

> Suggested location: `docs/adr/<NNNN>-<slug>.md`  
> Maintainer: the author proposing the decision or the module owner. Approver: Code Lead.  
> After copying: use the next available project number, fill in the placeholders, and remove template instructions. Retain historical ADRs; cross-reference a new decision and any decision it supersedes.

## When to use this template

- Use an ADR when a decision has lasting effects on module boundaries, important dependencies, public protocols, data storage, compatibility strategy, or a key algorithmic approach, and its trade-offs need a durable record.
- Ordinary fixes, implementation details within an existing design, and formatting changes do not require an ADR. Record sufficient reasoning in the task or design instead.
- Complete all sections below. For an inapplicable item, write `N/A` and a specific reason. An accepted ADR does not replace implementation instructions, tests, AI review, or Code Lead approval of the code.

## 1. Decision control

| Field | Value |
| --- | --- |
| ADR number / version | [Number] / [Version] |
| Status | Proposed / Accepted / Rejected / Superseded; start with Proposed |
| Author / participants | [Names and roles] |
| Proposal date | [Date] |
| Related task / design | `docs/tasks/<TASK-ID>/TASK.md` / `docs/design/<TASK-ID>.md` |
| Applicable code baseline | [Full SHA] |
| Supersedes / superseded by | [Repository-relative ADR paths, or N/A] |

## 2. Context and constraints

[Describe the problem requiring a decision, the current approach, verifiable evidence, and organizational and technical constraints. Explain why a brief implementation note in the task would not adequately preserve this decision.]

## 3. Selection criteria

| Criterion | Mandatory / trade-off | Basis |
| --- | --- | --- |
| [For example, compatibility scope, maintenance cost, or reproducibility] | [Category] | [Design requirement, baseline, or project constraint] |

## 4. Alternatives and evidence

| Option | Benefits | Costs and risks | Evidence / unverified assumptions | Conclusion |
| --- | --- | --- | --- | --- |
| Keep the current approach | [Benefits] | [Costs] | [Evidence] | [Reason to retain or reject] |
| [Option A] | [Benefits] | [Costs] | [Evidence] | [Reason to select or reject] |
| [Another option actually evaluated; remove this row if none] | [Benefits] | [Costs] | [Evidence] | [Conclusion] |

Do not present experiments that were not run, unverified performance, or assumed third-party capabilities as facts. Separate measurements from assumptions.

## 5. Decision

- Selection: [Specific technology, rule, or structure].
- Scope: [Modules, interfaces, versions, or scenarios].
- How it satisfies the criteria: [Key reasoning for each applicable criterion].
- Exceptions retained: [Boundaries and decision-maker for actual exceptions, or None].

While the status is Proposed, this section describes a proposed decision and does not authorize implementation that has not been approved.

## 6. Consequences and implementation

- Capabilities gained: [Benefits].
- Accepted costs and limits: [Maintenance, performance, or compatibility constraints].
- Required migration and documentation: [Tasks, owners, and contract/architecture paths].
- Verification: [How to establish that the decision meets its goals].
- Rollback or replacement: [How to exit this choice; explain if no practical rollback exists].
- Reassessment triggers: [Changes in scale, evidence, external constraints, or goals that require reconsideration].

## 7. Decision approval

| Document version | Code Lead | Decision | Time and time zone | Evidence of explicit approval or rejection | Conditions |
| --- | --- | --- | --- | --- | --- |
| [Version] | [Name] | Pending approval | [Pending] | [Actual record or Pending] | [Conditions or None] |

Change the status to Accepted or Rejected only when supported by an actual decision. A draft or AI recommendation is not a decision. When an accepted decision changes, create a new ADR and record the superseding relationship rather than overwriting historical reasoning.

## 8. Related material

- Architecture: `docs/architecture/OVERVIEW.md`.
- Contract: `docs/contracts/<contract>.md`, or N/A with a reason.
- External references / experiments: [Traceable sources, results, and versions, or None].

Related templates: [DESIGN_TEMPLATE.md](DESIGN_TEMPLATE.md), [ARCHITECTURE_TEMPLATE.md](ARCHITECTURE_TEMPLATE.md), [CONTRACT_TEMPLATE.md](CONTRACT_TEMPLATE.md).
