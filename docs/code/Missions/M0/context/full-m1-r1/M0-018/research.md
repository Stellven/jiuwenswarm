# Research and source decisions: M0-018

This support record informs [plan](plan.md), not a parallel normative design or acceptance gate.

| Decision | Rationale / source | Alternatives and implication |
| --- | --- | --- |
| Reuse existing Python/TypeScript/native adapters with missing governed behavior added explicitly | PRD/native integration obligations; architecture placement and source-only reuse evidence | A separate unrelated research framework would duplicate control surfaces; source compatibility still needs actual checks. |
| One owner for interface and evidence authority | TASK §4 and constitution single authorities | No duplicate contracts in optional support records; implementation schemas carry IF revision. |
| Protected verification/gating composition in M1 | USR-01 capsules/glossary; PRD 4.2 | General verifier-only operations may exist conceptually; mandatory product work still checks then gates through protected host. |
| Required upstream rubric adaptation | USR-02 guard-design; PRD 4.2.6; M0-007 | Exact upstream bodies/revision absent; adaptation cannot be claimed from generic prompts or source-only naming. |
| Truthful preparation state | Product code and runtime fixtures are not built by current request | PENDING_SOURCE blocks only dependent acceptance; unchecked work and NOT_RUN preserve actual status. |

Assigned original clauses:

- PRD 1.3 (../source/PRD - AI4Research.txt:L87-L210)
- PRD 1.5 (../source/PRD - AI4Research.txt:L262-L286)
- PRD 2.11 (../source/PRD - AI4Research.txt:L594-L619)
- PRD 3.4.7 (../source/PRD - AI4Research.txt:L924-L937)
- PRD 4.4 (../source/PRD - AI4Research.txt:L1797-L1807)
- PRD 4.4.1 (../source/PRD - AI4Research.txt:L1808-L1828)
- PRD 4.4.2 (../source/PRD - AI4Research.txt:L1829-L1836)
- PRD 4.4.3 (../source/PRD - AI4Research.txt:L1837-L1858)
- PRD 4.4.4 (../source/PRD - AI4Research.txt:L1859-L1866)
- PRD 4.4.5 (../source/PRD - AI4Research.txt:L1867-L1886)
- PRD 4.4.6 (../source/PRD - AI4Research.txt:L1887-L1894)
- PRD 4.4.7 (../source/PRD - AI4Research.txt:L1895-L1912)
- PRD 4.4.8 (../source/PRD - AI4Research.txt:L1913-L1934)
- PRD 4.4.9 (../source/PRD - AI4Research.txt:L1935-L1964)
- PRD 4.4.10 (../source/PRD - AI4Research.txt:L1965-L1997)
- PRD 5.4.3 (../source/PRD - AI4Research.txt:L2410-L2418)
- PRD 5.6.5 (../source/PRD - AI4Research.txt:L2498-L2518)
- PRD 6.11 (../source/PRD - AI4Research.txt:L2739-L2762)

Architecture reading:

- [offline-rsi.md](../source/build-package/offline-rsi.md)
- [placement.md#offline-rsi](../source/build-package/placement.md#offline-rsi)
- [capsules.md#verifier-internals-and-referee-protection](../source/build-package/capsules.md#verifier-internals-and-referee-protection)
- [failure-and-human.md#offline-rsi-is-a-separate-callback-policy](../source/build-package/failure-and-human.md#offline-rsi-is-a-separate-callback-policy)
- [delivery-phases.md#every-implementation-stage](../source/build-package/delivery-phases.md#every-implementation-stage)
- [capsule/declaration.md](../source/build-package/capsule/declaration.md)
- [principles.md#decisions-and-source-amendments](../source/build-package/principles.md#decisions-and-source-amendments)

Native reuse limitations: text-only Codex adapter; native Symphony exceptions/fallback/cache do not establish PASS; trajectory SQLite retention does not own run release; existing RSI journal/orchestrator is not hidden-oracle proof; JiuWenBox mechanisms require chosen-platform adversarial execution. Optional source/history/M1 links are historical; [current M0 register](../TASKS.md) and actual repository rules govern.
