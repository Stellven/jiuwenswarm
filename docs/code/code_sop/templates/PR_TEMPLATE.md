## Problem and outcome

<!-- Deploy to .github/pull_request_template.md. Every PR records the problem, scope, versions, verification, risks, and human decision. A small low-risk change may keep compact evidence here; complex tasks reference actual records rather than duplicating them. Explain N/A. Never check an item that has not been completed. A Draft PR is not permission to merge. -->

- Task: [TASK-ID and actual record path/link].
- Problem / trigger: [Fill in].
- Resulting behavior and acceptance source: [Describe the behavior; reference TASK version and AC identifiers without redefining thresholds].
- Risk level and rationale: [Low / medium / high; impact and recovery difficulty].
- Non-goals: [Fill in].

## Design authorization and scope

- Approved design / `write_code.md`: [Actual paths or TASK minimum-design section, versions, approver, evidence].
- Implementation plan: [Actual `docs/exec-plans/<TASK-ID>.md` or TASK brief-plan section; a small task still records its steps].
- Affected modules and owners: [Fill in].
- Author file-level understanding: [Actual FILE_MAP/checklist/TASK section, or list each file's responsibility, change, and downstream impact here].
- Interface, data, configuration, or dependency changes: [Fill in; confirm before stating unchanged].

## Branches and verified versions

- Source branch: [Actual `huawei_waterloo_xiaoyang`, `huawei_waterloo_saurav`, `huawei_waterloo_ramika`, `huawei_waterloo_muk`, or explicitly approved task branch].
- Target branch: `huawei_waterloo_main_branch`.
- Baseline B: [Full SHA, latest synchronization and verification time].
- Tested and reviewed implementation C: [Full SHA].
- Integration version or code tree actually tested: [Identifier and construction; disclose if untested].
- Relationship of this PR to those versions: [Identical / Later explanatory documentation only / Differences awaiting revalidation].

Reports and approval records may reference implementation C without containing their own commit SHA. Later explanatory documentation requires the file list, commit range, and actual diff verification. Changes affecting execution, tests, configuration, design, or acceptance do not qualify automatically. After implementation or baseline changes, revalidate affected scope and obtain Code Lead confirmation of approval applicability.

## Verification evidence

- Authoritative verification record: [Actual TEST_REPORT, TASK verification section, or this PR section; maintain results in one place].
- If the record is external, link to its commands and results. Otherwise complete the table below; do not create an empty report only to satisfy a reference.

| Working directory | Actual command / reproducible steps | Verified version | Actual result and exit code | Logs / artifacts |
| --- | --- | --- | --- | --- |
| [Fill in] | [Fill in command] | [C/B/integration version] | [Passed / Failed / Not run / Blocked and key output] | [Fill in] |

- Performance: [TASK threshold reference, measured baseline/current values, environment, repetitions, evidence; explain N/A].
- Unrun / failed / skipped checks: [Item, cause, impact, disposition, actual deferral if any; explicitly state none when supported].
- Later changes and baseline recheck: [Actual commands/results, relevant revalidation, updated versions].

## Review and human decision

- AI review: [Actual `docs/tasks/<TASK-ID>/review.md`; time, covered version, finding disposition].
- Code Lead function-level review: [Evidence for affected functions/call chains; explain N/A for documentation-only changes].
- Code Lead decision: [Pending approval / Changes requested / Approved / Rejected].
- Human approver / time / decision evidence: [Keep pending if no actual approval exists; identify an authorized independent reviewer when the Lead authored the change].
- Covered C/B and current-version check: [Fill in].

AI review precedes the final human review. AI is not an approver, and checkboxes do not replace a human decision.

## Risks and recovery

- Residual risks / known limitations: [Fill in].
- Compatibility / migration: [Fill in or explain N/A].
- Rollback method and recovery limits: [Explain data or external state that a code rollback cannot restore].
- Follow-up tasks and owners: [Fill in; deferred verification also needs a deadline and permitted-stage approval].
- Release or remote operations: [Record actual authorized scope; this template grants no execution authority].

## Before merging

- [ ] Design and implementation scope have human authorization; the author can explain every changed file.
- [ ] Verification covers current proposed content and baseline; required checks passed or have an explicit Code Lead deferral permitting merge.
- [ ] AI review is recorded; the Code Lead completed applicable function-level review.
- [ ] The specific version has human approval, all other prerequisites are satisfied, and no unresolved blocking finding or current acceptance failure is being bypassed.
- [ ] Recheck current baseline and commits; changes have appropriate revalidation and additional review.
- [ ] Preserve standing branch history through normal commits and merges; no force-push.
- [ ] Required documentation, handoff, and follow-up owners are identified; incomplete required follow-up verification prevents Done.

<!-- For full records, use IMPLEMENTATION_CHECKLIST_TEMPLATE.md, TEST_REPORT_TEMPLATE.md, REVIEW_TEMPLATE.md, and HANDOFF_TEMPLATE.md. After adoption, reference actual records or sections, not template filenames. -->

