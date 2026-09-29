# Tasks: DEMO-SYSTEM
**TASK**: [DEMO-SYSTEM](../../DEMO-SYSTEM/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/code_sop/examples/DEMO/specs/DEMO-SYSTEM-journey/

## Work Items
### Consumer block and integration
- [ ] T001 [US1] Bind paths and implement actual consumer wiring for B01; update plan.md with executable entries.
- [ ] T002 [US1] Assemble provider/consumer/check/configuration candidate and capture its identity; obtain DEMO-001/V03 boundary evidence.
### Whole-system verification
- [ ] T003 [US1] Execute V01 on the candidate and retain the actual run in evidence/.
- [ ] T004 [US1] Execute V02 in the same candidate session and retain the actual run in evidence/.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01,B02; DEMO-001/B01,B02; IF-001@r1 | T001,T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | Fictional example |
| [AC-002](spec.md) | B01,B02; IF-001@r1 | T001,T002 | V02 / T004 | NOT_RUN | None / NOT_BUILT | Requires same candidate/session |

## Dependency Order and Execution Notes
Consumer wiring can follow the IF definition. Final system checks follow valid provider block and boundary evidence. V02 follows V01 in the same session to expose stale-state defects.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No.
- Required AC/check coverage: 2 system ACs and 2 system V IDs, all NOT_RUN.
- Conclusion: NOT_READY.
- Remaining limitations: no implementation or runtime evidence.

## Evidence Invalidation
No existing evidence. A candidate change invalidates relevant system conclusions until impact assessment and required reruns.
