# Implementation checklist: [TASK-ID] — [Task title]

> Suggested location: `docs/tasks/<TASK-ID>/IMPLEMENTATION_CHECKLIST.md`. Use the full checklist for medium/high-risk work, changes across multiple files, or work across modules. Small, low-risk changes may keep applicable items in TASK or the PR. Version, design authorization, file understanding, verification evidence, and the status reference are required. Other items may use N/A with a specific reason. Checkboxes never replace evidence; all items start incomplete.

## 1. Identity, scope, and versions — required

- Task record: `docs/tasks/<TASK-ID>/TASK.md`.
- Author / module / Code Lead: [Fill in].
- Risk level and reason: [Low / medium / high; scope, failure consequences, recovery difficulty].
- Working branch: [Actual branch: `huawei_waterloo_xiaoyang`, `huawei_waterloo_saurav`, `huawei_waterloo_ramika`, `huawei_waterloo_muk`, or an explicitly approved task branch].
- Target branch: `huawei_waterloo_main_branch`.
- Synchronized and verified baseline B: [Full SHA, verification time, source].
- Verified implementation C: [Full SHA; write Pending verification if not yet available].
- Integration version or code tree actually tested: [Commit or reproducible construction; disclose if integration remains untested].
- Current task status: [Actual TASK-ID row/link in `docs/governance/CURRENT_STATUS.md`; maintain task state only there].

Committing a report changes HEAD. Reference checked implementation C, not the checklist's own commit SHA. If only explanatory documentation follows C, record its commit range, files, and actual diff check. Executable documentation, configuration, tests, dependencies, interfaces, thresholds, or code changes do not qualify for this exception. Baseline changes also require impact assessment.

## 2. Before implementation — required

- [ ] Read the root and all applicable path-level `AGENTS.md` files; record their paths: [Fill in].
- [ ] Confirm design scope, interfaces, non-goals, and acceptance thresholds; reference the design and authoritative TASK version/AC: [Fill in].
- [ ] The Code Lead's `docs/tasks/<TASK-ID>/write_code.md` covers this work; authorization evidence: [Name, time, record].
- [ ] An authorized human approved the design; approver / date / version: [Fill in; pause dependent implementation without approval].
- [ ] Inspect the working tree and preserve unrelated changes; record: [Clean, or files and handling].
- [ ] Synchronize the target branch and confirm B. Preserve standing branch history; do not force-push over it.
- [ ] Record the plan: [Actual `docs/exec-plans/<TASK-ID>.md` or TASK brief-plan section; do not replace a needed plan with N/A].

## 3. Author understanding of every changed file — required

The author must be able to explain each file; AI-generated descriptions do not replace understanding. Cover code, tests, dependencies, and configuration. Explanatory documentation may be grouped by purpose. If FILE_MAP or a TASK/PR section already holds this record, link to its exact section rather than maintaining a second copy.

Authoritative understanding record: [This table, or actual FILE_MAP/TASK/PR section].

| File | Previous responsibility and change | Callers / downstream impact | Preserved invariants / interfaces | Verification evidence | Author understanding |
| --- | --- | --- | --- | --- | --- |
| [Path] | [Fill in] | [Fill in] | [Fill in] | [Test or record] | [Pending explanation / confirmed with evidence] |

## 4. Implementation and risks — according to scope

| Check | Complete / Pending / N/A | Evidence or N/A reason |
| --- | --- | --- |
| Change follows approved design; deviations were approved first | [Fill in] | [Record and approved version] |
| Interfaces, errors, boundaries, and state transitions preserve the contract | [Fill in] | [Functions or tests] |
| Affected owners confirmed contracts across modules | [Fill in] | [Record or no cross-module impact] |
| Data handling, permissions, logs, and external calls follow task constraints | [Fill in] | [Paths or risk rationale] |
| Migration, compatibility, and rollback are executable | [Fill in] | [Rehearsal or no persistent-data changes] |
| Performance changes meet pre-agreed measured thresholds | [Fill in] | [Actual report section or reason not applicable] |
| Dependencies, generated files, and configuration are necessary and reproducible | [Fill in] | [Pinned versions or generation command] |
| Temporary debugging is removed; unrelated refactoring is excluded | [Fill in] | [Diff scope] |
| Lasting rules, contracts, and task progress are updated | [Fill in] | [Actual paths] |

## 5. Verification and review gates — required

- [ ] Run the checks required for the current stage on C and baseline B; evidence: [Actual TEST_REPORT, TASK verification section, or PR section].
- [ ] Disclose failures, unrun checks, blockers, and residual risks. Approved deferrals reference their actual approval and permitted stage; planned execution is not a pass.
- [ ] AI review exists in `docs/tasks/<TASK-ID>/review.md`, with actual scope, findings, and limits.
- [ ] Findings are fixed or explicitly adjudicated by the Code Lead; related checks were rerun after fixes.
- [ ] The Code Lead understands affected functions, call relationships, and risks, with a human review record.
- [ ] The Code Lead made a version-specific final decision; AI conclusions are not human approval.
- [ ] Recheck code and baseline before merge; update evidence and approval applicability after changes.

Later explanatory documentation: [Commit range after C, files, actual command such as `git diff --name-status <C>..HEAD`, result, and acceptance impact].

## 6. Delivery conclusion — required

- Completed scope: [Fill in].
- Incomplete or blocked items: [Fill in; state none only with supporting scope/evidence].
- Remaining risks and owners: [Fill in].
- Next executor and action: [Fill in].
- Human merge decision: [Pending / Approved / Rejected; approver, time, evidence, covered C and B].

Related templates: [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [REVIEW](REVIEW_TEMPLATE.md), [PR](PR_TEMPLATE.md), [HANDOFF](HANDOFF_TEMPLATE.md).

