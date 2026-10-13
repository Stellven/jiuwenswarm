# ADR-0001: Native Codex runtime with Jiuwen-owned application coordination

Template: [ADR_TEMPLATE](../code/code_sop/templates/ADR_TEMPLATE.md).

## 1. Decision control

| Field | Value |
| --- | --- |
| ADR number / version | 0001 / 0.1 |
| Status | Proposed |
| Author / participants | Xiaoyang with Codex drafting/research support; affected owners pending |
| Proposal date | 2026-09-28 |
| Related task / design | [TASK](../code/Missions/AI4R-001/TASK.md) / [native plan v0.1](../code/Missions/AI4R-001/plan.md), pending approval |
| Applicable code baseline | dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 |
| Supersedes / superseded by | N/A — first proposed ADR; no previous ADR directory existed |

## 2. Context and constraints

The user selects Codex App Server with personal local subscription login, fresh first use and no model-provider keys. Existing main agents use Model/DeepAgent; external members already have CodexHarness support. Replacing the execution boundary affects durable ownership of tools, sessions, approval, orchestration and auxiliary calls, so the rationale needs an ADR rather than a task checkbox.

## 3. Selection criteria

| Criterion | Mandatory / trade-off | Basis |
| --- | --- | --- |
| App Server subscription-only operation | Mandatory | spec FR-002/006, AC-06 |
| All agreed capabilities preserved or explicitly re-scoped | Mandatory | FR-004/009, AC-08 |
| Correct interaction/session ownership | Mandatory | AC-02/03/07 |
| Reuse actual code and bound maintenance | Trade-off | Existing harness and gateway/session layers |

## 4. Alternatives and evidence

| Option | Benefits | Costs and risks | Evidence / unverified assumptions | Conclusion |
| --- | --- | --- | --- | --- |
| Keep current account provider | Small change | Direct auth/HTTP path and other provider consumers remain | research C01–C20 | Does not meet objective |
| Generic ModelClient bridge | Keeps DeepAgent | Tool-result/held-turn semantics unproven | DeepAgent consumes returned tool calls; App Server owns ongoing turns | Not selected without separate proof |
| Native harness + host MCP + narrow text/JSON port | Reuses real integration while preserving app coordination | Main/leader rail parity and auxiliary/capability gaps | Installed harness/MemberRuntime seams; G1–G4 unresolved | Proposed |
| Rewrite app coordination into Codex | One execution layer | Loses existing scheduling/team contracts; broader scope | No parity evidence | Reject as initial approach |

## 5. Decision

- Selection proposed: native CodexSessionAdapter, scoped host MCP tools, account lifecycle owner, and explicit auxiliary text/JSON port.
- Scope: runtime/gateway/settings and all model consumers; no legacy import.
- Criteria: policy enforces chosen auth/transport; existing app owns identity and coordination; coverage gate prevents silent feature removal.
- Exceptions retained: none. Unproven capability rows are blockers, not approved omissions.

## 6. Consequences and implementation

- Capabilities gained: one auditable subscription execution policy and managed account lifecycle.
- Costs/limits: permissions/rails must be mapped; pinned private SDK hooks need fail-closed checks; embeddings/media not yet solved.
- Migration/documentation: operational caller rewiring and new profile only; legacy-data conversion N/A under CR-01. Update architecture, runtime contract and task evidence.
- Verification: plan G1–G4, quickstart Q1–Q6, provider-construction/outbound traps and actual local account scenarios.
- Rollback/replacement: stop new runtime on failure; preserve separate profile; no automatic key-based fallback. Revisit a bridge only after proof and revised design.
- Reassessment triggers: unresolved capability parity, unsupported SDK change, missing permission guarantees, or changed user requirements.

## 7. Decision approval

| Document version | Code Lead | Decision | Time and time zone | Evidence of explicit approval or rejection | Conditions |
| --- | --- | --- | --- | --- | --- |
| 0.1 | Xiaoyang | Pending | Pending | [Plan approval record](../code/Missions/AI4R-001/plan.md#8-approval-record--required) | Resolve prerequisite gates; no approval inferred from requirements confirmation |

## 8. Related material

- [Architecture](../architecture/build-package/README.md).
- [Draft runtime contract](../code/Missions/AI4R-001/contracts/runtime.md).
- [Research and protocol evidence](../code/Missions/AI4R-001/research.md); no live model proof performed.
