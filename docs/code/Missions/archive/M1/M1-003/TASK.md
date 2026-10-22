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


### M1-C019 current maintained-source integration

M1-C019 / 2026-10-21: Explicit user request: connect the complete maintained-design POC workflow to native web chat. Include qualified intake, Intent/Requirements compiler, accepted Research Brief, bounded DAG Planner, Search, Screening, Hypothesis, Builder/Benchmark POC, Evaluation and Delivery. Every work Capsule retains declared deterministic checks, independent verifier, mechanically validated assessment, protected gate and frozen routing. Current authority is docs/architecture/design-package/ and docs/product/received-prds/prd-m1-reviewed-2026-10-13.txt (SHA256 890c63ee4849d61e8c7ddc980891985d57c59005ca6c62be45957c59e82782de, 255245 bytes), replacing historical frozen-source allocation for this change. Existing evidence remains historical; direct chat is not workflow acceptance. Required focused boundary and connected-journey verification supersedes C010 only for this request; unrelated campaigns remain excluded. Owners: M1-001 startup/executor/model; M1-002 library/binder/gates/scheduler; M1-003 compiler; M1-004 research Capsules; M1-005 routing; M1-006 native web; M1-SYSTEM integration and current evidence. Admission bypasses, invented metrics and manufactured PASS records are prohibited.


### M1-C020 verifier disclosure decision

M1-C020 / 2026-10-21: Explicit user decision: semantic verification uses only pinned CC declaration and exact output content, with fixed input-independent instructions/criteria. Hide user input, original/reference documents, accepted predecessor content, producer conversation, policy/observations/review manifest and any reference-lookup capability from the semantic assessor. Preserve host deterministic source/identity checks, read-only independent verifier, mechanical assessment validation and protected committed gates. Do not claim hidden-input fidelity or external evidence verification. Input-aware versus output-only comparison is deferred; no automatic alternate mode. This supersedes C019's proposed input-aware verifier expansion, not the complete integrated POC workflow. Full and compact maintained design guard/compiler/reference/principle/decision records are synchronized. No declaration schema or existing IF payload revision changes: retain the existing declaration/output-only verifier boundary.


### M1-C021 assigned-source functional delivery

M1-C021 / 2026-10-21: The user explicitly selects docs/code/Missions/M1/source/Architecture_Design for completing the entire user journey in the one existing app chat, and explicitly requests subagents for acceleration. This assignment supersedes C019's package selection for this work; frozen inputs remain unmodified and explicit authorized C001-C020 decisions remain in force, especially GPT-6.1 Sol and declaration/output-only semantic assessor inputs. Continue existing C019 AC/work identities and owner TASKs; no parallel feature or standalone report. Exact source clarification: reference/node-execution.md fixes one work group per research node, while reference/run-plan.md fixes separate Builder/Benchmark nodes; POC is the task grouping, not a newly invented enclosing parent. Existing per-node gates and predecessor commits must actually control execution. Local functional development may use an immutable tool-free Builder release (bounded file-text model output, trusted mechanical packaging; no generated tools or exposed credentials) and an explicitly CPU-compatible local Benchmark release/profile; old tool-using/GPU-required releases remain pinned and native GB10/ARM64 qualification remains unaccepted. This is no permission to fabricate a measurement, admission, host observation or qualification. Independently preregistered guard calibration and actual model provenance remain required. A versioned private static calibration fixture can carry authored input/output case bytes without claiming a product invocation; its limitations and unexercised physical predicates remain explicit. Owners: 001 scientific/local startup and model, 002 activation/calibration/binder/scheduling, 003 compiler, 004 research CCs, 005 frozen routing, 006 native chat, SYSTEM final actual user journey. Avoid broad test campaigns and large D-drive artifacts.


### M1-C023 ? user-authorized PDF-only paper summary (2026-10-21)
User explicitly requested immediate delivery of an actual PDF-only summary in the existing app, following the offered bounded Compiler ? Planner ? paper-summary Capsule ? independent output-only Verifier/deterministic checks/Gate ? Delivery chain. This adds a separate protected document policy and two read-only Capsules; no baseline, dataset, GPU, network or scientific execution is required or claimed. Existing POC policy, required stages, scientific contracts and historical outcomes remain unchanged. Owner004 defines M1-IF-017@r1;005 consumes it for planning/binding;002 owns core composition;003 owns new extraction page boundaries;006 consumes accepted results in the original native chat;SYSTEM observes the supplied ModelLakeFishing PDF through the real app path. Broad tests/qualification remain user-directed NOT_RUN. Existing native directories are retained; this paragraph is scope allocation, not acceptance.


### M1-C024 / C025 - user-requested POC activation and latest PDF failure (2026-10-21)
C024: User accepted the prepared Python classification request and explicitly said "do POC". Resume full protected POC configuration and one ordinary native user request through actual Compiler/Planner/Search/Screening/Hypothesis/Builder/Benchmark/Evaluation/Delivery, with unchanged declaration/output-only verifiers, deterministic checks and gates. Owning002 captures independent local POC runtime/config and fixes concrete integration failures;004 owns scientific worker/measurement boundary;SYSTEM owns actual request/result/history/export. Existing003/005/006/007 APIs and obligations remain compatible consumers, not new authorities. Preserve working5174 PDF and5173 old instances; use isolated5175 state/credentials/IPC/workspace/executor. No image/dependency builds, qualification campaigns, benchmark suites or extra report/archive copies. Existing four benchmark cases remain implemented. C025: user reports latest5174 summary failed despite earlier positive C023. Trace that exact original user request and fix its actual stopping cause; earlier success never establishes all-input reliability. Allocate relevant002/003/004 code and SYSTEM observation; preserve user uploads, original failure and accepted C023 report. Any semantic/interface change requires owner-native amendment before source edits.
