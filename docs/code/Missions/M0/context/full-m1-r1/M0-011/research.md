# Research and source decisions: M0-011

This support record informs [plan](plan.md), not a parallel normative design or acceptance gate.

| Decision | Rationale / source | Alternatives and implication |
| --- | --- | --- |
| Reuse existing Python/TypeScript/native adapters with missing governed behavior added explicitly | PRD/native integration obligations; architecture placement and source-only reuse evidence | A separate unrelated research framework would duplicate control surfaces; source compatibility still needs actual checks. |
| One owner for interface and evidence authority | TASK §4 and constitution single authorities | No duplicate contracts in optional support records; implementation schemas carry IF revision. |
| Protected verification/gating composition in M1 | USR-01 capsules/glossary; PRD 4.2 | General verifier-only operations may exist conceptually; mandatory product work still checks then gates through protected host. |
| Required upstream rubric adaptation | USR-02 guard-design; PRD 4.2.6; M0-007 | Exact upstream bodies/revision absent; adaptation cannot be claimed from generic prompts or source-only naming. |
| Truthful preparation state | Product code and runtime fixtures are not built by current request | PENDING_SOURCE blocks only dependent acceptance; unchecked work and NOT_RUN preserve actual status. |

Assigned original clauses:

- PRD 3.4 (../source/PRD - AI4Research.txt:L868-L873)
- PRD 3.4.1 (../source/PRD - AI4Research.txt:L874-L883)
- PRD 3.4.2 (../source/PRD - AI4Research.txt:L884-L890)
- PRD 3.4.3 (../source/PRD - AI4Research.txt:L891-L897)
- PRD 3.4.4 (../source/PRD - AI4Research.txt:L898-L904)
- PRD 3.4.5 (../source/PRD - AI4Research.txt:L905-L916)
- PRD 3.4.6 (../source/PRD - AI4Research.txt:L917-L923)
- PRD 3.4.7 (../source/PRD - AI4Research.txt:L924-L937)
- PRD 4.2.1 (../source/PRD - AI4Research.txt:L1314-L1354)
- PRD 4.2.6 (../source/PRD - AI4Research.txt:L1483-L1513)
- PRD 4.4.3 (../source/PRD - AI4Research.txt:L1837-L1858)
- PRD 5.2.1 (../source/PRD - AI4Research.txt:L2310-L2327)

Architecture reading:

- [m1-design.md](../source/build-package/m1-design.md)
- [workflow.md](../source/build-package/workflow.md)
- [contracts-and-native-reuse.md](../source/build-package/contracts-and-native-reuse.md)
- [guard-design.md](../source/build-package/guard-design.md)
- [placement.md](../source/build-package/placement.md)
- [failure-and-human.md](../source/build-package/failure-and-human.md)
- [offline-rsi.md](../source/build-package/offline-rsi.md)

Native reuse limitations: text-only Codex adapter; native Symphony exceptions/fallback/cache do not establish PASS; trajectory SQLite retention does not own run release; existing RSI journal/orchestrator is not hidden-oracle proof; JiuWenBox mechanisms require chosen-platform adversarial execution. Optional source/history/M1 links are historical; [current M0 register](../TASKS.md) and actual repository rules govern.
