# Review record: [TASK-ID]

> Suggested location: `docs/tasks/<TASK-ID>/review.md`. Complete AI review first, then Code Lead function-level review and the final human decision. Small changes may use a shorter record with equivalent evidence. Versions, scope, findings, limits, and the human conclusion are required; explain N/A. AI reports findings and recommendations, never signs approval. Creating this file does not complete a review.

## 1. Review target — required

- Task / author / module: [Fill in].
- Risk level and rationale: [Fill in].
- Working branch: [Actual personnel branch or explicitly approved task branch].
- Target branch: `huawei_waterloo_main_branch`.
- Reviewed implementation C: [Full SHA].
- Target baseline B: [Full SHA, source, and verification time].
- Actual diff / working directory / command reviewed: [Comparison range, directory, exact command].
- Implementation or integration version actually tested: [Match the actual verification record].
- Acceptance source: [TASK version and AC identifiers; do not redefine thresholds here].
- Design authorization: [Actual design or TASK minimum-design section, `write_code.md` version, approver, and evidence].
- Verification evidence: [Actual TEST_REPORT, TASK verification section, or PR section].
- Author file-level understanding: [Actual FILE_MAP, checklist, TASK, or PR section].

Review the actual proposed diff, not only the task description or AI summary. Disclose whether uncommitted changes are included and how to reproduce the reviewed content. Reference real files/sections; simplified tasks do not need extra empty reports or checklists.

## 2. AI review — complete first

- Execution time / tool or model: [Fill in; do not guess unknown details].
- Files and scope actually read: [Fill in].
- Commands actually executed and results: [Directory, command, exit code, evidence; explicitly state if none were run].
- Coverage: [Relevant design/architecture/contract compliance, correctness, failure paths, test adequacy, performance evidence].
- Unreviewed areas and limits: [For example, missing environment/data or no dynamic verification].

### Findings

| ID | Severity | File / function / location | Trigger and actual impact | Verifiable evidence | Recommendation | Finding status |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | [Blocking / Important / Suggestion] | [Fill in] | [Specific input, call, or runtime condition] | [Reproduction, code path, or logs] | [Fill in] | [Open / Pending verification / Fixed / Adjudicated] |

- **Blocking:** an approved-design violation, critical correctness or data-integrity issue, or required acceptance failure. Resolve it before merge.
- **Important:** a concrete behavioral, compatibility, performance, or maintainability risk. Fix it or obtain an authorized, documented disposition.
- **Suggestion:** an improvement that does not affect current acceptance; the Code Lead may explicitly assign a follow-up task.

If no issues are found, say "No issues found within the stated scope"; do not claim the system is defect-free. Mark insufficiently evidenced concerns as unconfirmed rather than presenting assumptions as facts.

AI conclusion: [Recommend human review / Recommend fixes first / Review blocked; basis and limitations].

## 3. Author response and revalidation — required; explain N/A if no findings

| Finding ID | Response or disagreement | Fix commit | Revalidation command / result / evidence | Additional AI review | Human disposition |
| --- | --- | --- | --- | --- | --- |
| R-01 | [Fill in] | [SHA] | [Working directory and actual result] | [Time and covered version] | [Pending / actual Code Lead decision] |

When fixes change code, update C and related test evidence; do not carry forward an old pass without assessing the new version. Retain the original findings and resolution history.

## 4. Code Lead function-level review — human confirmation required

The Code Lead must explain changed functions and affected key call chains: responsibilities, inputs/outputs, invariants, failure modes, and test coverage. Do not rereview unrelated repository functions solely for this task; match scope to risk. Documentation-only changes may state N/A for function changes while retaining content review. If the Code Lead is the author, identify the authorized independent human reviewer and authorization evidence.

| File / function / call chain | Relationship to approved design | Inputs/outputs / invariants / failure paths | Callers and cross-module impact | Test and performance evidence | Human review opinion |
| --- | --- | --- | --- | --- | --- |
| [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Fill in] | [Pending / actual opinion] |

- Author understanding checked: [Discussion evidence or files requiring clarification].
- Unresolved findings and tradeoffs: [Risk acceptance requires a responsible person and basis].
- Affected module owners' opinions: [Evidence or N/A reason].
- Compliance with approved regression, compatibility, and measured-performance requirements: [Conclusion and evidence].

## 5. Final human decision — required; initially pending

- Decision: **[Pending approval / Changes requested / Approved to merge / Rejected]**.
- Code Lead or authorized independent reviewer / time and timezone: [Actual decision-maker].
- Approval evidence: [PR review link or auditable human confirmation].
- Covered implementation C / baseline B / integration result: [Explicit versions].
- Conditions and owners: [Unmet prerequisites prevent Ready to merge].
- Deferred items and follow-up: [Actual CHANGE_REQUEST, permitted stage, owner, deadline, and failure response; or none].

Required checks must pass or have formal Code Lead approval to defer the specified check. A deferral must explicitly state the stage it permits: permission to continue implementation does not permit merging. Unresolved blocking findings or failure of the current acceptance criteria cannot be bypassed solely by a check deferral. Acceptance changes require an approved design/requirements change and renewed verification. Keep deferred checks visibly incomplete; the task cannot be Done until required follow-up verification is complete.

AI may faithfully transcribe an existing human decision and cite its source, but may not invent approval or treat generation/commit of this file as agreement.

## 6. Version check before merge — required

This record may reference reviewed implementation C; it need not contain its own commit SHA. Later explanatory documentation requires a recorded range, files, actual diff check, and impact assessment. Design, acceptance, code, tests, configuration, dependency, or target-baseline changes require appropriate revalidation and additional review, with Code Lead confirmation of the current version. Conflict resolution is new code to review.

| Check | Current facts and evidence | Effect on original approval | Required action / completion |
| --- | --- | --- | --- |
| Commits and files changed after C | [Directory, diff command, result] | [Fill in] | [Fill in] |
| Current target baseline versus B | [Latest SHA, time, source] | [Fill in] | [Fill in] |
| Revalidation and additional review | [New version and actual evidence] | [Fill in] | [Fill in] |

Merge eligibility at this review time: [Yes / No / Pending verification]. Recorder / time / evidence: [Fill in]. Maintain live task state only in the TASK-ID row of `docs/governance/CURRENT_STATUS.md`.

Related templates: [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [PR](PR_TEMPLATE.md), [CHANGE_REQUEST](CHANGE_REQUEST_TEMPLATE.md).

