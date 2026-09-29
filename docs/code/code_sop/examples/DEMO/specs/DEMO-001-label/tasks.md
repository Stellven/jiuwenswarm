# Tasks: DEMO-001
**TASK**: [DEMO-001](../../DEMO-001/TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/code_sop/examples/DEMO/specs/DEMO-001-label/

## Work Items
### Foundation / shared definitions
- [ ] T001 [US1] Bind real provider and test paths/runtime in plan.md if implementation is requested.
### Block B01 and B02
- [ ] T002 [US1] Implement B01/B02 according to AC-001/002 at the paths established by T001.
- [ ] T003 [US1] Execute V01/V02 and store actual run records in evidence/.
### Connected boundaries
- [ ] T004 [US1] After DEMO-SYSTEM/T001, execute V03 and store actual boundary evidence in evidence/.
### System contribution
- [ ] T005 [US1] Supply provider candidate identity and current evidence to DEMO-SYSTEM's native matrix.

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01 | T002 | V01 / T003 | NOT_RUN | None / NOT_BUILT | Fictional example |
| [AC-001](spec.md) | IF-001@r1 | T002 | V03 / T004 | NOT_RUN | None / NOT_BUILT | Needs consumer wiring |
| [AC-002](spec.md) | B02 | T002 | V02 / T003 | NOT_RUN | None / NOT_BUILT | Fictional example |
| [AC-002](spec.md) | IF-001@r1 | T002 | V03 / T004 | NOT_RUN | None / NOT_BUILT | Needs consumer wiring |

## Dependency Order and Execution Notes
T001 -> T002 -> T003; V03 requires consumer wiring; final system acceptance follows boundary verification. Do not execute this toy scope without an implementation request.

## Current Verification Conclusion
- Candidate identity: NOT_BUILT.
- Required work complete: No.
- Required AC/check coverage: 2 ACs, 3 V IDs, all NOT_RUN.
- Conclusion: NOT_READY.
- Remaining limitations: no executable implementation.

## Evidence Invalidation
No existing runtime evidence. A future interface change must invalidate boundary and downstream system results.
