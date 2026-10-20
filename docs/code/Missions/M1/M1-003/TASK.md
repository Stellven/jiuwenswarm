# TASK: M1-003 - Ingestion and complete Intention Compiler

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-003 / r3 / 2026-10-16 |
| Parent TASKS | [M1 register](../TASKS.md) |
| Executor / collaborators | Codex; read-only source reviewers collaborate under the same scope |
| Requested outcome and instruction/source | Qualified uploaded inputs through Intent and Requirements CCs to gate-accepted Research Brief; [invoked user prompt](../source/Code/prompt.txt) |
| Included scope / exclusions | Core Phase 1. No commit, push, merge or deployment is implied. Broader statistical benchmark campaigns and automatic live RSI activation are excluded. |
| PRD clause and architecture node references | PRD 3.1, 3.2, 4.7, 6.5; architecture pipeline/intention-compiler.md, reference/intent-and-requirements.md. Exact bytes: [source baseline](../source-baseline.json). |
| Working checkout / branch / base | D:/research/ai_for_research/runs/jiuwenswarm / ai4r_M1 / 3f8cc21cb4b497b844821dfec10a4b9e7140f9a4; supplied Code and QA were initially untracked |
| Affected code/document paths | jiuwenswarm/research/ (proposed compiler integration), tests/; this TASK's native artifacts |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-003/ | One directory for this TASK |
| spec.md | [spec.md](spec.md) | AC authority; reviewed Specify/Clarify r3 (C008) |
| plan.md | [plan.md](plan.md) | Design/procedures; generated and source-aligned in Plan r3 |
| tasks.md | [tasks.md](tasks.md) | Sole work/progress and AC-to-evidence authority; generated in Tasks r2 |
| evidence/ | evidence/ | Actual runs only; no runtime acceptance from registration |
| Supporting artifacts | [Program source baseline](../source-baseline.json) | Source identity; subordinate to registered authorities |

Native artifacts are created only during their corresponding Spec Kit phases. spec.md r3 and reviewed plan.md r3 now exist; tasks.md r2 now records the ordered implementation/verification work and evidence matrices. M1-IF-002@r2 is consumed under C008; unchanged owned interfaces remain r1. Registration or a specification does not establish implementation or acceptance.

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| M1-001, M1-002; minimal authenticated API contract from M1-006 | Adopt the supplied contracts with one owning TASK per interface | Definitions before dependent plan; real implementation/resources before boundary/system verification | Plan blocks: M1-003/B01, M1-003/B02, M1-003/B03, M1-003/B04, M1-003/B05; native work IDs and AC/V evidence correspondence: tasks.md |

Contract-definition order is distinct from implementation order. Define M1-006's minimal client boundary and M1-001/002 shared seams early; full shell integration does not gate independent compiler/research preparation.

## 4. Embedded cross-module agreements

### M1-IF-004 at r1 - Qualified intake, Intent and accepted Research Brief

This TASK adopts the exact frozen referenced field/schema contracts by reference as its canonical agreement. Required fields, types, units, validation and compatibility are those pinned definitions plus the explicit amendments below; this is not a parallel paraphrased schema. Generated schemas will implement this IF/revision during the ordered planning/implementation phases.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M1-003; M1-006 supplies controlled upload records -> M1-002 binder, M1-004, M1-005, M1-006, M1-QA |
| Purpose / source requirement | reference/intent-and-requirements.md; reference/field-catalog.md qualified-intake/resource-snapshot/default-policy; pipeline/intention-compiler.md; exact file bytes and versions are pinned by [source-baseline.json](../source-baseline.json). Locators above are relative to the supplied source/Architecture_Design package unless explicitly QA. |
| Inputs: fields, types, units, required/optional, validation | Original UTF-8 request and valid code-point spans, live authorized uploaded document/project/dataset refs, separate source/resource inventories, protected default policy and frozen interaction mode; optional prior infeasibility linkage. Adopted type/version set: qualified-intake2, intent-ir schema1, research-brief schema2, resource-inventory/resource-snapshot/default-policy1; client-upload from M1-IF-007 |
| Outputs: fields, types, units, semantics, guarantees | Accepted internal Intent then one externally accepted Research Brief with mandatory outcomes, constraints/preferences, targets/deliverables/acceptance/evidence/default attribution; or explicit unresolved/halt records and retained rejected items. |
| States and invariants | Requirements starts only after accepted Intent. Preserve every mandatory item or explicit unresolved disposition. Defaults cannot invent purpose, resolve conflicting mandatory requirements or claim observed hardware. Uploaded-only scope and D48/D50 apply; fixed fallback is independent of conditional advanced module. |
| Errors, timeout, retry, cancellation | Invalid/empty/out-of-range span, missing required resource, raw/deleted/foreign upload or material unresolved meaning blocks affected acceptance. Optional rejected files stay recorded and never reach worker inputs. Wall/invocation limits and reliable mandatory token enforcement apply without fabricated telemetry. |
| Side effects and idempotency | Capture immutable qualified inputs and candidate/accepted compiler artifacts through M1-IF-003; no browsing, cloning, dataset download or post-start Brief editing. Same client identity reconciles through M1-IF-007. |
| Compatibility and migration | Research Brief remains2.0.0 and Requirements IR its alias. Conditional advanced compiler consumes/emits adopted compatible bindings only; unavailable alternate-lane/module source stays explicit rather than inventing schemas. |
| Machine-readable schema / source path | [Critical schema catalog](../source/Architecture_Design/reference/catalog.json) and [field contracts](../source/Architecture_Design/reference/field-contracts.json), with referenced owning pages; generated implementation schemas are not created yet. Sidecar records use their owning benchmark-runner tables. |
| Provider/consumer verification responsibilities | Provider and consumer procedures are mapped to qualified V IDs in plan.md Verification Design. tasks.md owns their AC-to-work/evidence correspondence. No runtime PASS is established by design. |
| Open agreement questions | No unresolved product-intent question. Actual endpoint/credential/hardware/custody availability remains an execution prerequisite only for the paths that require it. Internal implementation/framing is selected in plan without widening this agreement. |

Consumed agreements: [M1-IF-001@r1](../M1-001/TASK.md#4-embedded-cross-module-agreements), [M1-IF-002@r2](../M1-002/TASK.md#4-embedded-cross-module-agreements), [M1-IF-003@r1](../M1-002/TASK.md#4-embedded-cross-module-agreements), [M1-IF-007@r1](../M1-006/TASK.md#4-embedded-cross-module-agreements).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-C003 / 2026-10-16 | Invoked prompt supplies full-M1 snapshot and all-phases implementation plus separate four-case QA scope; supersedes earlier compiler-only assignment for this request | Current TASK scope and parent source allocation | Historical AI4R-001/DEVTOOLS results unchanged; no acceptance reused | Codex / current user request |
| M1-I003 / 2026-10-16 | Source-resolved implementation binding: Bounded fallback and conditional advanced compiler. The fixed scientific compiler remains bounded/noninteractive. Submission mode permits bounded supported clarification only during intake; headless uses supplied answers or halts, and every run is unattended after intake. Missing external advanced compiler/alternate-lane binding is a named conditional dependency, not a reason to invent a schema or omit fixed compilation. Source: PRD3.2/4.7/6.12; D5/D33/D48/D50 | Owning spec and IF r1; affected blocks/checks and work/evidence correspondence are mapped in plan.md/tasks.md | No prior M1 runtime evidence; consumers adopt this same canonical binding | Codex / source-specific reconciliation, not a fabricated new user approval |
| M1-C008 / 2026-10-16 | Approved aggregate worker-plus-verifier library ceilings; canonical semantics in M1-002/TASK.md M1-C008/M1-IF-002@r2 | M1-003 budget-related FR/AC and plan/tasks; IF003/004/006 shapes and copied aggregate meaning unchanged | Invalidate affected library snapshot, authored static-template/configuration/candidate pins and budget/check evidence; retain original records and source examples | Codex / explicit user answer in current session |

Progress belongs in tasks.md when generated. Registration is not implementation, integration or verification.
