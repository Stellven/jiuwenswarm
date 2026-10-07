> **Historical AI4R-001 record:** identities, decisions and observations below retain their original scope. Current M1 design and registration use the repository design-package and M1 TASKS; old review/approval cards do not govern new v2 work.

# Implementation checklist: AI4R-001 - Subscription login/basic-chat milestone

Version: 0.3. Template: [IMPLEMENTATION_CHECKLIST_TEMPLATE](https://github.com/Stellven/jiuwenswarm/blob/918df5e4081ed35d53257dfccd33119a7b639c57/docs/code/code_sop/templates/IMPLEMENTATION_CHECKLIST_TEMPLATE.md). This records research and the authorized M1 product stage, not whole-project completion.

## 1. Identity, scope, and versions — required

- Task record: [TASK v0.8](TASK.md), Section 4 decision records.
- Artifact mode and authority register: Spec Kit; TASK Section 1/4.
- Requirements / design / execution sources: spec v0.2, plan/tasks v0.3 in specs/AI4R-001-codex-subscription; R001-R004 and M001-M006.
- Author / module / Code Lead: Xiaoyang / frontend/backend subscription milestone / Xiaoyang; AI drafting support.
- Risk level and reason: overall task high risk; M1 changes production account, process, session and frontend paths; live account acceptance remains unverified.
- Working branch: ai4r_xiaoyang.
- Target branch: ai4r_main_branch; no delivery in this stage.
- Synchronized and verified baseline B: dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483; fresh origin/ai4r_main_branch fetch on 2026-09-28 matches this baseline; exact time not retained.
- Verified implementation C: pending implementation commit; HEAD is baseline B plus uncommitted M1 files fingerprinted in TEST_REPORT, not a committed implementation.
- Integration version or code tree actually tested: working tree M1 on B, fake-provider application facade/history tests plus real signed-out process probe; full launcher/socket fixture journey passed; browser/live account pending.
- Current task status: [AI4R-001 in CURRENT_STATUS](../../governance/CURRENT_STATUS.md).

## 2. Before implementation — required

- [x] Read root AGENTS.md, jiuwenswarm/channels/web/AGENTS.md and frontend/AGENTS.md, TASK, native artifacts and directive.
- [x] Confirm M1 scope against spec v0.2 and plan v0.3 addendum; no lowered whole-project acceptance thresholds.
- [x] Code Lead directive covers presented login/basic-chat work: [write_code v0.9](write_code.md), TASK Section 4 continuation evidence.
- [x] Human authorized the presented bounded milestone; unpresented implementation details and final code are not claimed human-reviewed.
- [x] Working tree inspected; historical SOP/preparation changes preserved; current product edits are explicitly included in FILE_MAP/report.
- [x] Team baseline fetched and unchanged at B/HEAD; no merge necessary at this checkpoint. No remote force push.
- [x] Native plan.md/tasks.md v0.3 own design and ordered progress; no duplicate backlog.
- [x] Pinned Spec Kit mapping/prerequisites checked; 11/14 requirements items checked, three broader gaps explicit; no extension hooks. M1 does not waive G1-G4.

## 3. Author understanding of every changed file — required

Authoritative understanding record: [FILE_MAP](FILE_MAP.md), Sections 2-4. It contains historical research and 32 M1 file entries with function/call-chain explanations. Xiaoyang's personal understanding and function review remain pending; AI-generated explanations do not establish them.

## 4. Implementation and risks — according to scope

| Check | Complete / Pending / N/A | Evidence or N/A reason |
| --- | --- | --- |
| Change follows approved design; deviations were approved first | Complete for bounded scope; full design unresolved | TASK continuation, plan v0.3 M1; explicit launcher/text-only stage, unchanged spec |
| Interfaces, errors, boundaries, and state transitions preserve the contract | Partial | Runtime contract v0.3; fixtures pass; synthetic socket journey passes; restart/live recovery incomplete |
| Affected owners confirmed contracts across modules | Xiaoyang coordinates; independent review pending | User explicitly requested frontend/backend changes; no other owner's opinion invented |
| Data handling, permissions, logs, and external calls follow task constraints | Partial evidence | Sanitized child, account checks, log-body removal, profile lock; full signed-in audit pending |
| Migration, compatibility, and rollback are executable | Pending; legacy migration N/A | CR-01, fresh-root fixture; startup passes; rollback/browser/restart continuation unverified |
| Performance changes meet pre-agreed measured thresholds | N/A for current evidence | No approved numerical threshold or performance improvement claimed; no benchmark |
| Dependencies, generated files, and configuration are necessary and reproducible | Complete for bounded checks | Existing pinned Codex0.144.4/Node22/Python3.11; locks unchanged; manifest and probe retained |
| Temporary debugging is removed; unrelated refactoring is excluded | Complete for M1 scope | Retained verification scripts deliberate; temporary Vite process stopped; earlier user documentation preserved |
| Lasting rules, contracts, and task progress are updated | Complete for recorded stage | plan/tasks/directive, contract, report, FILE_MAP and bounded review updated |

## 5. Verification and review gates — required

- [ ] All current-stage required checks complete: bounded tests/build/process checks pass in TEST_REPORT v0.8, but M005 startup/socket verification now passes; browser verification remains incomplete.
- [x] Failures, unrun checks and residual risks disclosed; no approved deferrals invented.
- [x] Bounded diff/source AI review exists in [review.md](review.md); it is not final whole-diff review.
- [ ] All findings resolved/adjudicated: R-01-R-03 corrected with revalidation; R-04/R-05 remain open.
- [ ] Code Lead's personal function understanding remains pending in FILE_MAP and review.
- [ ] Version-specific final human decision remains pending; independent reviewer unassigned.
- [ ] Code/baseline recheck before merge remains pending; no delivery attempted.

Later explanatory documentation: report/checklist/review/status and record-pointer updates after executable checks; no new executable changes covered by that exception. Manifest and documentation/diff checks identify the current scope; no implementation commit exists.

## 6. Delivery conclusion — required

- Completed scope: historical R001-R004; M001-M004 bounded M1 implementation/fixtures as recorded in native tasks. No whole-project acceptance pass.
- Incomplete or blocked items: M005 browser verification, M006 live account, restart recovery, full feature/platform replacement and final review/delivery.
- Remaining risks and owners: Xiaoyang coordinates G1-G4 and acceptance; shared transport failure affects active streams and old threads cannot resume after process restart. Neither is waived.
- Next executor and action: AI continues product integration verification; Xiaoyang participates in personal sign-in when ready. Implementation progress is solely in native tasks.md.
- Human merge decision: Pending; no implementation commit, independent final review, PR or merge.

### Subsequent demo acceptance and publication (2026-09-28)

Xiaoyang accepted localhost:5173 and requested direct publication. Implementation C: `97c1bd6930497c2a97cedeca82c49b62650b56c8`; post-commit verification is in TEST_REPORT T-50–T-53. Earlier pending-delivery statements are historical for this demo; unchecked whole-project/independent-review gates are not silently marked passed. The explicit publication decision is in TASK Section 4, and the run guide and remaining work are in HANDOFF.
