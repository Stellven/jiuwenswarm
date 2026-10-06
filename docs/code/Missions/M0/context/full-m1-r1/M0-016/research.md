# Research and source decisions: M0-016

This support record informs [plan](plan.md), not a parallel normative design or acceptance gate.

| Decision | Rationale / source | Alternatives and implication |
| --- | --- | --- |
| Reuse existing Python/TypeScript/native adapters with missing governed behavior added explicitly | PRD/native integration obligations; architecture placement and source-only reuse evidence | A separate unrelated research framework would duplicate control surfaces; source compatibility still needs actual checks. |
| One owner for interface and evidence authority | TASK §4 and constitution single authorities | No duplicate contracts in optional support records; implementation schemas carry IF revision. |
| Protected verification/gating composition in M1 | USR-01 capsules/glossary; PRD 4.2 | General verifier-only operations may exist conceptually; mandatory product work still checks then gates through protected host. |
| Required upstream rubric adaptation | USR-02 guard-design; PRD 4.2.6; M0-007 | Exact upstream bodies/revision absent; adaptation cannot be claimed from generic prompts or source-only naming. |
| Truthful preparation state | Product code and runtime fixtures are not built by current request | PENDING_SOURCE blocks only dependent acceptance; unchecked work and NOT_RUN preserve actual status. |

Assigned original clauses:

- PRD 3.9 (../source/PRD - AI4Research.txt:L1146-L1151)
- PRD 3.9.1 (../source/PRD - AI4Research.txt:L1152-L1159)
- PRD 3.9.2 (../source/PRD - AI4Research.txt:L1160-L1167)
- PRD 3.9.3 (../source/PRD - AI4Research.txt:L1168-L1174)
- PRD 3.9.4 (../source/PRD - AI4Research.txt:L1175-L1189)
- PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354)
- PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513)
- PRD 4.9.3 (../source/PRD - AI4Research.txt:L2223-L2236)
- PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327)
- PRD 6.9 (../source/PRD - AI4Research.txt:L2700-L2717)

Architecture reading:

- [m1-design.md](../source/build-package/m1-design.md)
- [workflow.md](../source/build-package/workflow.md)
- [contracts-and-native-reuse.md](../source/build-package/contracts-and-native-reuse.md)
- [guard-design.md](../source/build-package/guard-design.md)
- [placement.md](../source/build-package/placement.md)
- [failure-and-human.md](../source/build-package/failure-and-human.md)

Native reuse limitations: text-only Codex adapter; native Symphony exceptions/fallback/cache do not establish PASS; trajectory SQLite retention does not own run release; existing RSI journal/orchestrator is not hidden-oracle proof; JiuWenBox mechanisms require chosen-platform adversarial execution. Optional source/history/M1 links are historical; [current M0 register](../TASKS.md) and actual repository rules govern.
