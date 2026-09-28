# AI4Research Working Constitution

Version: 0.1.0 | Effective for AI4R-001 preparation: 2026-09-28 | Process owner: Xiaoyang

Authority: the existing Code SOP v1.1 and Xiaoyang's explicit instruction in this conversation to start AI4R-001 using Spec Kit. This adoption preserves the seven principles exactly. It does not claim an independent final review, completed team-wide pilot, or approval of a technical design that has not been written.

## 1. The seven governing principles

1. **Approve the design before implementation.** Establish the objective, boundaries, interfaces, and acceptance criteria before writing the implementation. Obtain Code Team Lead approval. Small changes may use a short design record; material changes require an updated design and approval covering the new scope.
2. **Use one team integration branch and individual working branches.** Synchronize with the latest team integration branch before starting. Code entering it must undergo testing, AI review, and Code Team Lead review.
3. **Humans must understand the code.** Authors must explain every changed file. The Code Team Lead must understand affected functions, call chains, and system consequences. Authors remain accountable for AI-generated code.
4. **Maintain root and local AGENTS.md files as durable human–AI context.** The Code Team Lead owns the root instructions; module owners maintain local instructions. These provide reliable entry points to design, architecture, contracts, responsibilities, environment, status, plans, checklists, and tests.
5. **Implement against the Code Team Lead's write_code.md.** This document defines the task's implementation authorization and boundaries. Read it together with applicable AGENTS files and the approved design.
6. **Complete the agreed verification before requesting formal review.** Provide traceable evidence for the current implementation. A Draft PR may support early collaboration; it must not become Ready for review before the applicable gates are met.
7. **AI reviews first; the human lead decides afterward.** AI produces a structured review.md record. After the author addresses findings, the Code Team Lead makes the final decision for the current version. An AI recommendation is not merge approval.

## 2. Artifact authority

Read root and applicable local AGENTS, then the task's registry and directive. TASK registers the feature directory and branch. Native spec.md owns requirements and stable AC identifiers; plan.md owns technical design; tasks.md owns ordered work and progress. The task's write_code.md records actual execution authority. TEST_REPORT records real verification, review.md records AI findings and the subsequent human decision, and CURRENT_STATUS holds the current task state.

Use the existing SOP DESIGN and PLAN templates as completeness prompts in the native artifacts. Do not create competing design, plan, acceptance, or progress documents. Shared contracts and architecture remain authoritative for shared behavior.

## 3. Scope and workflow

- Application: Stellven/jiuwenswarm. Team integration and PR base: ai4r_main_branch. Personal work uses the assigned ai4r branch.
- Feature selection is independent of Git branch naming. Keep the feature pointer local and ignored. No optional Git extension or automatic branch/commit hooks are adopted.
- The Lead's existing explicit authorization covers the actions it specifies. Do not invent approvals, and do not request authorization again for already covered work.
- Define requirements, investigate existing code, write the technical plan and work items, analyze consistency, and identify the design version and directive before implementation.
- Required risk-proportionate checks must appear in generated task lists. Upstream optional-test defaults do not waive the verification gate.
- Authors inspect every changed file. Native analysis, checklists, task boxes, and convergence reports do not replace actual tests, AI diff review, or a human merge decision.
- If the Lead is also the author, appoint an independent qualified human for final review. That later review requirement does not block authorized setup and research.
- Material scope/contract changes need a concrete change decision; ordinary choices within existing authority do not need repeated approval. Keep technical gaps and blocked checks visible.
- Record evidence against implementation and integration-base versions. Do not mark Done before the applicable post-merge, follow-up verification, and handoff requirements are complete.
- Keep authentication material outside tracked files, normal logs, and frontend application state. Do not replace subscription sign-in with copied tokens in source or configuration.

## 4. Amendments

Xiaoyang owns process amendments. Record the reason, affected scope, actual human decision, effective version, and migration impact. Changes to the seven principles require a separately identified SOP policy change; tooling initialization or generated constitution text cannot alter them. Preserve existing applicable local instructions and record any conflict against the specific task authorization.

## 5. Entry points

- [Code SOP](../../docs/code/Code_SOP.md)
- [Root instructions](../../AGENTS.md)
- [Task registry](../../docs/tasks/AI4R-001/TASK.md)
- [Current status](../../docs/governance/CURRENT_STATUS.md)
- [Environment and tooling](../../docs/governance/ENVIRONMENT.md)
- [Spec Kit workflow](../../docs/code/code_sop/SPEC_KIT_WORKFLOW.md)
