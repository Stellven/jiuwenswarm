# TASK: M1-005 - Bounded dynamic planning

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-005 / r4 / 2026-10-19 |
| Parent TASKS | [M1 register](../TASKS.md) |
| Executor / collaborators | Codex; read-only source reviewers collaborate under the same scope |
| Requested outcome and instruction/source | Planner proposal, protected validation and frozen planned execution with static baseline preserved; [invoked user prompt](../source/Code/prompt.txt) |
| Included scope / exclusions | Phase 3 implementation; targeted full verification, not independent core release gate. No commit, push, merge or deployment is implied. Broader statistical benchmark campaigns and automatic live RSI activation are excluded. |
| PRD clause and architecture node references | PRD 4.8, 6.12; architecture reference/capsules/planner.md, reference/run-plan.md. Exact bytes: [source baseline](../source-baseline.json). |
| Working checkout / branch / base | D:/research/ai_for_research/runs/jiuwenswarm / ai4r_M1 / 3f8cc21cb4b497b844821dfec10a4b9e7140f9a4; supplied Code and QA were initially untracked |
| Affected code/document paths | jiuwenswarm/research/ (proposed native Leader/SwarmFlow adaptation), tests/; this TASK's native artifacts |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-005/ | One directory for this TASK |
| spec.md | [spec.md](spec.md) | r3; original authority/IDs retained, I032 planned-consumer compatibility |
| plan.md | [plan.md](plan.md) | r4; original authority/IDs retained, I032 planned-consumer compatibility |
| tasks.md | [tasks.md](tasks.md) | r3; original authority/IDs retained, I032 planned-consumer compatibility |
| evidence/ | evidence/ | Actual runs only; no runtime acceptance from registration |
| Supporting artifacts | [Program source baseline](../source-baseline.json) | Source identity; subordinate to registered authorities |

Native artifacts are created only during their corresponding Spec Kit phases. spec.md r3 and reviewed plan.md r2 now exist; tasks.md r2 now records the ordered implementation/verification work and evidence matrices. M1-IF-002@r2 is consumed under C008; unchanged owned interfaces remain r1. Registration or a specification does not establish implementation or acceptance.

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| M1-002 binder and library definitions; M1-003 Brief; M1-004 admitted research CCs for integrated execution | Adopt the supplied contracts with one owning TASK per interface | Definitions before dependent plan; real implementation/resources before boundary/system verification | Plan blocks: M1-005/B01, M1-005/B02, M1-005/B03, M1-005/B04; native work IDs and AC/V evidence correspondence: tasks.md |

Contract-definition order is distinct from implementation order. Define M1-006's minimal client boundary and M1-001/002 shared seams early; full shell integration does not gate independent compiler/research preparation.

## 4. Embedded cross-module agreements

### M1-IF-006 at r1 - Bounded Planner proposal

This TASK adopts the exact frozen referenced field/schema contracts by reference as its canonical agreement. Required fields, types, units, validation and compatibility are those pinned definitions plus the explicit amendments below; this is not a parallel paraphrased schema. Generated schemas will implement this IF/revision during the ordered planning/implementation phases.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M1-005 -> M1-002 binder/check/gate; M1-006 inspection; M1-SYSTEM |
| Purpose / source requirement | reference/capsules/planner.md; reference/run-plan.md; D30/D39/D47; exact file bytes and versions are pinned by [source-baseline.json](../source-baseline.json). Locators above are relative to the supplied source/Architecture_Design package unless explicitly QA. |
| Inputs: fields, types, units, required/optional, validation | Accepted Brief, exact admitted library/resource snapshots and protected plan policy; user selects planned before the run. Adopted type/version set: plan-proposal:field-contract:3/version3.0.0; shared PlanNode/PlanInput/PlanOutput/CoverageEntry/Limits from exact sources |
| Outputs: fields, types, units, semantics, guarantees | One data-only bounded proposal with concrete Brief coverage, declared nodes/bindings/dependencies/limits, or the prescribed single INFEASIBLE: line at most300characters; no graph on infeasibility. |
| States and invariants | Proposal grants no authority/check relief, invents no CC and chooses no model. One work CC per proposed node, source policy ceilings and one Delivery leaf. Static selectors are not proposal IDs. Both plan modes use M1-IF-003 protected freeze/dispatch. |
| Errors, timeout, retry, cancellation | Invalid/infeasible graph dispatches no research node; protected validation decides acceptance. Only eligible first planned infeasibility permits one linked new compiler attempt, no third; static or runtime/model/budget faults create no such automatic attempt. |
| Side effects and idempotency | Planner performs its source-bounded single model call and returns data; it executes no research tools/effects. Rejected history is retained. Explicit plan_source never silently changes. |
| Compatibility and migration | Adopt proposal3.0.0, not retired PlannedSubnode/version2. Node counts exclude pre-plan compiler/planner. Native Leader integration must honor the same contract. |
| Machine-readable schema / source path | [Critical schema catalog](../source/Architecture_Design/reference/catalog.json) and [field contracts](../source/Architecture_Design/reference/field-contracts.json), with referenced owning pages; generated implementation schemas are not created yet. Sidecar records use their owning benchmark-runner tables. |
| Provider/consumer verification responsibilities | Provider and consumer procedures are mapped to qualified V IDs in plan.md Verification Design. tasks.md owns their AC-to-work/evidence correspondence. No runtime PASS is established by design. |
| Open agreement questions | No unresolved product-intent question. Actual endpoint/credential/hardware/custody availability remains an execution prerequisite only for the paths that require it. Internal implementation/framing is selected in plan without widening this agreement. |

Consumed agreements: [M1-IF-002@r2](../M1-002/TASK.md#4-embedded-cross-module-agreements), [M1-IF-003@r1](../M1-002/TASK.md#4-embedded-cross-module-agreements), [M1-IF-004@r1](../M1-003/TASK.md#4-embedded-cross-module-agreements), [M1-IF-005@r1](../M1-004/TASK.md#4-embedded-cross-module-agreements).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-C003 / 2026-10-16 | Invoked prompt supplies full-M1 snapshot and all-phases implementation plus separate four-case QA scope; supersedes earlier compiler-only assignment for this request | Current TASK scope and parent source allocation | Historical AI4R-001/DEVTOOLS results unchanged; no acceptance reused | Codex / current user request |
| M1-I005 / 2026-10-16 | Source-resolved implementation binding: Planner infeasibility and policy scope. When no admitted CC covers a mandatory obligation, return the prescribed single INFEASIBLE: line (maximum 300 characters), no graph and no invented CC. Plan-node ceilings exclude pre-plan Compiler and Planner nodes. At most one linked new compiler attempt follows eligible planned infeasibility; other failures never silently switch plan_source. Source: reference/capsules/planner.md Producer obligations/Failure outcomes; reference/run-plan.md; D30/D39 | Owning spec and IF r1; affected blocks/checks and work/evidence correspondence are mapped in plan.md/tasks.md | No prior M1 runtime evidence; consumers adopt this same canonical binding | Codex / source-specific reconciliation, not a fabricated new user approval |
| M1-C008 / 2026-10-16 | Approved aggregate worker-plus-verifier library ceilings; canonical semantics in M1-002/TASK.md M1-C008/M1-IF-002@r2 | M1-005 budget-related FR/AC and plan/tasks; IF003/004/006 shapes and copied aggregate meaning unchanged | Invalidate affected library snapshot, authored static-template/configuration/candidate pins and budget/check evidence; retain original records and source examples | Codex / explicit user answer in current session |

Progress belongs in tasks.md when generated. Registration is not implementation, integration or verification.


### M1-I032 direct planned-execution consumer reconciliation

IF001r2 and IF003r3 retain the original public plan/proposal/node/subnode/model fields and ordinary r1 semantics consumed by this Planner. IF016 has no direct producer/consumer reference in the current Planner native records, and this path cannot claim private evaluation authority. Pre-plan Planner remains its exact 120-second/one-call/zero-tool worker plus independent reserved review, without a planned RunPlan lease inspector or new scientific resource grant. The accepted Brief/library/resource/policy identities, frozen snapshot timing and graph/source/budget/coverage checks remain unchanged. A model proposal or PlanNode resource label never acquires a native lease or authority. For full planned scientific execution in existing V11, the actual002 Scheduler/Runner and004 scientific host adapters MUST consume owning001 IF001r2 before first whole-parent worker/start, use the shared physical-resource ledger across static/planned/ordinary/private aliases, and retain ownership through whole-attempt terminal plus actual cessation. Planned mode cannot bypass this via an alternate runner, call-time lock, new execution ID or static fallback. Missing actual native/resource/Builder/kernel services blocks the required journey and cannot pass from a valid graph or model-only Planner component.

The single field/behavior authorities remain owning001 IF001r2 and owning002 IF003r3/IF016r2, not a duplicated Planner agreement. Existing AC003/004/006 and T012/T013/T019/T023, V07/V08/V11 preserve their source obligations; construct independent no-bypass/zero-start negatives before dependent integration, and require current actual resources for V11. New protocol checks remain NOT_RUN/UNBUILT and earlier component evidence stays scoped. Spec r3 and owned IF006r1 are unchanged; no new product/source field, threshold, AC, T or V ID is introduced.


### M1-C019 current maintained-source integration

M1-C019 / 2026-10-21: Explicit user request: connect the complete maintained-design POC workflow to native web chat. Include qualified intake, Intent/Requirements compiler, accepted Research Brief, bounded DAG Planner, Search, Screening, Hypothesis, Builder/Benchmark POC, Evaluation and Delivery. Every work Capsule retains declared deterministic checks, independent verifier, mechanically validated assessment, protected gate and frozen routing. Current authority is docs/architecture/design-package/ and docs/product/received-prds/prd-m1-reviewed-2026-10-13.txt (SHA256 890c63ee4849d61e8c7ddc980891985d57c59005ca6c62be45957c59e82782de, 255245 bytes), replacing historical frozen-source allocation for this change. Existing evidence remains historical; direct chat is not workflow acceptance. Required focused boundary and connected-journey verification supersedes C010 only for this request; unrelated campaigns remain excluded. Owners: M1-001 startup/executor/model; M1-002 library/binder/gates/scheduler; M1-003 compiler; M1-004 research Capsules; M1-005 routing; M1-006 native web; M1-SYSTEM integration and current evidence. Admission bypasses, invented metrics and manufactured PASS records are prohibited.


### M1-C021 assigned-source functional delivery

M1-C021 / 2026-10-21: The user explicitly selects docs/code/Missions/M1/source/Architecture_Design for completing the entire user journey in the one existing app chat, and explicitly requests subagents for acceleration. This assignment supersedes C019's package selection for this work; frozen inputs remain unmodified and explicit authorized C001-C020 decisions remain in force, especially GPT-6.1 Sol and declaration/output-only semantic assessor inputs. Continue existing C019 AC/work identities and owner TASKs; no parallel feature or standalone report. Exact source clarification: reference/node-execution.md fixes one work group per research node, while reference/run-plan.md fixes separate Builder/Benchmark nodes; POC is the task grouping, not a newly invented enclosing parent. Existing per-node gates and predecessor commits must actually control execution. Local functional development may use an immutable tool-free Builder release (bounded file-text model output, trusted mechanical packaging; no generated tools or exposed credentials) and an explicitly CPU-compatible local Benchmark release/profile; old tool-using/GPU-required releases remain pinned and native GB10/ARM64 qualification remains unaccepted. This is no permission to fabricate a measurement, admission, host observation or qualification. Independently preregistered guard calibration and actual model provenance remain required. A versioned private static calibration fixture can carry authored input/output case bytes without claiming a product invocation; its limitations and unexercised physical predicates remain explicit. Owners: 001 scientific/local startup and model, 002 activation/calibration/binder/scheduling, 003 compiler, 004 research CCs, 005 frozen routing, 006 native chat, SYSTEM final actual user journey. Avoid broad test campaigns and large D-drive artifacts.


### M1-C023 ? user-authorized PDF-only paper summary (2026-10-21)
User explicitly requested immediate delivery of an actual PDF-only summary in the existing app, following the offered bounded Compiler ? Planner ? paper-summary Capsule ? independent output-only Verifier/deterministic checks/Gate ? Delivery chain. This adds a separate protected document policy and two read-only Capsules; no baseline, dataset, GPU, network or scientific execution is required or claimed. Existing POC policy, required stages, scientific contracts and historical outcomes remain unchanged. Owner004 defines M1-IF-017@r1;005 consumes it for planning/binding;002 owns core composition;003 owns new extraction page boundaries;006 consumes accepted results in the original native chat;SYSTEM observes the supplied ModelLakeFishing PDF through the real app path. Broad tests/qualification remain user-directed NOT_RUN. Existing native directories are retained; this paragraph is scope allocation, not acceptance.
