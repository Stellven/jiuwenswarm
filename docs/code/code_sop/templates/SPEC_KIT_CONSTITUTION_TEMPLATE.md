# AI4Research Constitution

> Template for `.specify/memory/constitution.md` at the application repository root. Before adoption, fill factual fields and reconcile existing instructions. Preserve the seven principles below exactly; they are copied from `docs/code/Code_SOP.md`. This template is not a ratified constitution or an implementation authorization.

| Governance field | Actual record |
| --- | --- |
| Status | Draft; pending Lead ratification |
| Constitution version | [Version assigned at adoption] |
| Governing SOP version and immutable reference | [Version and commit/link for `docs/code/Code_SOP.md`] |
| Process owner / authorized independent delegate | [Actual names and roles] |
| Ratified by / date and timezone / decision evidence | Pending ratification / pending / pending |
| Last amendment / rationale / decision evidence | [None at initial adoption, or actual record] |
| Validated Spec Kit version / integration | [Recorded version, source commit, and integration from ENVIRONMENT] |

## 1. The seven governing principles

1. **Approve the design before implementation.** Establish the objective, boundaries, interfaces, and acceptance criteria before writing the implementation. Obtain Code Team Lead approval. Small changes may use a short design record; material changes require an updated design and approval covering the new scope.
2. **Use one team integration branch and individual working branches.** Synchronize with the latest team integration branch before starting. Code entering it must undergo testing, AI review, and Code Team Lead review.
3. **Humans must understand the code.** Authors must explain every changed file. The Code Team Lead must understand affected functions, call chains, and system consequences. Authors remain accountable for AI-generated code.
4. **Maintain root and local AGENTS.md files as durable human–AI context.** The Code Team Lead owns the root instructions; module owners maintain local instructions. These provide reliable entry points to design, architecture, contracts, responsibilities, environment, status, plans, checklists, and tests.
5. **Implement against the Code Team Lead's write_code.md.** This document defines the task's implementation authorization and boundaries. Read it together with applicable AGENTS files and the approved design.
6. **Complete the agreed verification before requesting formal review.** Provide traceable evidence for the current implementation. A Draft PR may support early collaboration; it must not become Ready for review before the applicable gates are met.
7. **AI reviews first; the human lead decides afterward.** AI produces a structured review.md record. After the author addresses findings, the Code Team Lead makes the final decision for the current version. An AI recommendation is not merge approval.

## 2. Authority and instruction scope

The SOP owns team policy. This constitution expresses its unchanged governing principles for Spec Kit and links to the operative records; it does not create an independent approval system. Read applicable root and local `AGENTS.md`, the TASK registry, the approved specification/design, shared contracts, and the Lead's task-specific `write_code.md` before implementation.

If generated skills, hooks, templates, or an amendment conflict with the SOP or current task authority, record the conflict and pause dependent actions for the Lead's decision. Continue independent authorized work. Do not silently select weaker gates. AI may draft requirements, designs, plans, and decisions, but only a real authorized human can approve the relevant scope.

## 3. Repository and branch rules

- Application repository: `Stellven/jiuwenswarm`.
- Team integration branch and PR base: `ai4r_main_branch`.
- Persistent personal branches: `ai4r_xiaoyang`, `ai4r_saurav`, `ai4r_ramika`, and `ai4r_muk`.
- Synchronize through the adopted `docs/code/code_sop/GIT_WORKFLOW.md`. Preserve uncommitted work and shared history; do not force-push or substitute the repository's default branch for the team integration branch.
- One pending task per persistent personal branch. Extra task branches require the Lead's recorded agreement. A Spec Kit feature directory is not permission to create or switch a Git branch.
- Keep the optional upstream Git extension and automatic branch/commit/push actions disabled unless a separate approved workflow amendment explicitly adopts them.

## 4. Artifact mode and sources of truth

Each task registers exactly one mode, `Manual` or `Spec Kit`, in `docs/tasks/<TASK-ID>/TASK.md`, together with its author, risk path, branch, baseline, exact artifact paths, and approval references. Existing tasks do not migrate automatically. For Spec Kit tasks:

| Fact | Sole authoritative record |
| --- | --- |
| Task identity, artifact routing, owners, risk, approval references | `docs/tasks/<TASK-ID>/TASK.md` |
| Requirements, non-goals, and stable AC identifiers | `<registered-feature-directory>/spec.md` |
| Feature design and verification strategy | `<registered-feature-directory>/plan.md` |
| Implementation steps, dependencies, progress, discoveries, remaining work | `<registered-feature-directory>/tasks.md` |
| Shared approved interfaces | `docs/contracts/<contract>.md` |
| Implementation authority and limits | `docs/tasks/<TASK-ID>/write_code.md` |
| SOP gates | `docs/tasks/<TASK-ID>/IMPLEMENTATION_CHECKLIST.md` |
| Actual verification commands/results and covered versions | `docs/tasks/<TASK-ID>/TEST_REPORT.md` |
| Actual AI findings and subsequent human decision | `docs/tasks/<TASK-ID>/review.md` |
| Current team task state | `docs/governance/CURRENT_STATUS.md` |

Use DESIGN and PLAN templates as completeness prompts within native artifacts; do not maintain duplicate feature designs in `docs/design/` or duplicate implementation plans in `docs/exec-plans/`. Feature `contracts/` files are candidate changes or references, not replacements for shared approved contracts. Label their status and reference the shared version. Architecture, ADRs, code maps, environment, testing strategy, and handoff retain their adopted locations.

Record acceptance criteria as stable `AC-01`, `AC-02`, etc. Specify evaluation methods, datasets, baselines, environments, and thresholds before implementation where relevant. Missing evidence requires investigation, not invented targets. Manual tasks retain the paths and proportionate records defined by the SOP.

## 5. Required lifecycle and evidence

1. Confirm instructions, feature selection, branch, baseline, environment, and known failures. The TASK registry determines the feature path; keep `.specify/feature.json` local and untracked. A mutable selector does not establish authority.
2. Define and clarify requirements in `spec.md`; prepare `plan.md` with applicable DESIGN content. Draft `tasks.md` using applicable PLAN content, explicitly request the agreed verification tasks, and analyze consistency. Upstream optional-test defaults cannot waive team checks. Drafting tasks does not authorize executing them.
3. Obtain human design approval for the actual spec/plan versions and task scope, then the Lead's `write_code.md`, specifying allowed scope, paths, contracts, checks, and stop conditions. Record affected-owner confirmations when required. Refine subsequent tasks only inside that authorization or obtain approval for the changed scope.
4. Implement within authorization. The author reads every changed file and maintains file/function/caller understanding. Use CHANGE_REQUEST for material scope, requirement, contract, architecture, or threshold changes; pause dependent work until the revised scope is approved.
5. Run the agreed checks, inspect outcomes, and record commands, working directories, environment, implementation SHA, baseline SHA, logs, and limits. Distinguish Passed, Failed, Skipped, Not run, and Blocked; do not claim work-in-progress evidence establishes final merge readiness.
6. AI reviews the actual diff, callers, contracts, and evidence. The author resolves findings, reruns affected checks, and obtains follow-up AI review after changes. The Lead or authorized independent human then reviews affected functions/call chains and decides for the covered version.
7. Confirm current head/base, valid approval, required checks and permitted deferrals, then integrate using the adopted PR workflow. Verify the actual merge, update state, and complete handoff. Outstanding required verification prevents Done.

A generated checklist, `analyze` result, `converge` conclusion, completed task checkbox, or successful command exit is not an approval or substitute for evidence. Converge can append remediation tasks; review their authority before implementation. Installed hooks and implementation helpers can mutate files/configuration, so inspect their proposed and actual scope.

Later changes follow the SOP's evidence-validity rules. A results-only record commit may refer to the tested implementation SHA after confirming its diff changes no relevant behavior, configuration, tests, contracts, or acceptance criteria. Documentation affecting those authorities can invalidate previous evidence.

Simplified tasks keep the short manual path and every governing gate. A formal Lead deferral must identify the permitted stage, reason, alternative evidence, risk, verification owner, deadline, and recovery trigger. It cannot conceal known blocking defects or current acceptance failures. Permission to continue implementation does not imply permission to merge.

## 6. Amendments and compliance review

The Code Team Lead owns amendments. A proposed amendment identifies the reason, affected principles/rules, compatibility impact, new version, migration steps, and actual decision evidence. Spec Kit upgrades and generated constitution updates remain proposals until reviewed; the generator must not invent ratification or amendment dates.

Use a version scheme recorded at adoption: major for incompatible governance changes, minor for added obligations, and patch for clarifications that do not change obligations. A version label alone does not establish approval. Preserve superseded policy/design references so reviewers can identify what governed existing tasks.

Any proposed change to the seven principles must be a separately approved SOP policy change; routine Spec Kit adoption must preserve them. Before ratification or amendment, reconcile this file, the SOP, AGENTS, affected skills/templates, task mappings, and adoption records. Record the human approver, effective version/date, affected tasks, and verified links.

## 7. Adopted entry points

Replace placeholders with real paths and immutable versions where needed. Do not mark adoption complete while required fields remain pending.

- SOP: `docs/code/Code_SOP.md` at [version/commit].
- Spec Kit adapter: `docs/code/code_sop/SPEC_KIT_WORKFLOW.md` at [version/commit].
- Root / applicable module instructions: `AGENTS.md` / [actual module paths].
- Ownership / environment / testing / status: [actual adopted `docs/governance/` files].
- Architecture / shared contracts / code map: [actual paths and relevant versions].
- Active task registry / authorization: [TASK path] / [write_code path and approved version].
- Adoption and pilot evidence: [actual checklist/PR/TASK references, or pending].
