# TASK: M1-004 - Research pipeline and scientific execution

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-004 / r6 / 2026-10-20 |
| Parent TASKS | [M1 register](../TASKS.md) |
| Executor / collaborators | Codex; read-only source reviewers collaborate under the same scope |
| Requested outcome and instruction/source | Search through Delivery, static template, prepared environment lock/provisioning, bounded POC, scientific positive/negative/inconclusive results; [invoked user prompt](../source/Code/prompt.txt) |
| Included scope / exclusions | Core Phase 1. No commit, push, merge or deployment is implied. Broader statistical benchmark campaigns and automatic live RSI activation are excluded. |
| PRD clause and architecture node references | PRD 3.3-3.9, 4.9, 6.6-6.9; architecture pipeline/stages.md, reference/capsules/. Exact bytes: [source baseline](../source-baseline.json). |
| Working checkout / branch / base | D:/research/ai_for_research/runs/jiuwenswarm / ai4r_M1 / 3f8cc21cb4b497b844821dfec10a4b9e7140f9a4; supplied Code and QA were initially untracked |
| Affected code/document paths | jiuwenswarm/research/ (proposed research CCs), tests/; this TASK's native artifacts |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-004/ | One directory for this TASK |
| spec.md | [spec.md](spec.md) | r4; existing authority/IDs retained, I032/I033 consumer compatibility and evidence correspondence |
| plan.md | [plan.md](plan.md) | r6; existing authority/IDs retained, I032/I033 consumer compatibility and evidence correspondence |
| tasks.md | [tasks.md](tasks.md) | r5; existing authority/IDs retained, I032/I033 consumer compatibility and evidence correspondence |
| evidence/ | evidence/ | Actual runs only; no runtime acceptance from registration |
| Supporting artifacts | [Program source baseline](../source-baseline.json) | Source identity; subordinate to registered authorities |

Native artifacts are created only during their corresponding Spec Kit phases. spec.md r2 and reviewed plan.md r2 now exist; tasks.md r1 records the ordered implementation/verification work and evidence matrices. Each IF retains its exact revision listed in this TASK. Registration or a specification does not establish implementation or acceptance.

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| M1-001, M1-002, M1-003; frozen shell API from M1-006 | Adopt the supplied contracts with one owning TASK per interface | Definitions before dependent plan; real implementation/resources before boundary/system verification | Plan blocks: M1-004/B01, M1-004/B02, M1-004/B03, M1-004/B04, M1-004/B05, M1-004/B06, M1-004/B07, M1-004/B08, M1-004/B09, M1-004/B10, M1-004/B11; native work IDs and AC/V evidence correspondence: tasks.md |

Contract-definition order is distinct from implementation order. Define M1-006's minimal client boundary and M1-001/002 shared seams early; full shell integration does not gate independent compiler/research preparation.

## 4. Embedded cross-module agreements

### M1-IF-005 at r1 - Research artifacts, scientific protocol and empirical evidence

This TASK adopts the exact frozen referenced field/schema contracts by reference as its canonical agreement. Required fields, types, units, validation and compatibility are those pinned definitions plus the explicit amendments below; this is not a parallel paraphrased schema. Generated schemas will implement this IF/revision during the ordered planning/implementation phases.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M1-004; protected preparation/provisioner/executor own locks and runtime receipts -> M1-002, M1-005, M1-006, M1-008, M1-QA, M1-SYSTEM |
| Purpose / source requirement | reference/capsules/search.md; reference/capsules/screening.md; reference/capsules/hypothesis.md; reference/capsules/builder.md; reference/capsules/research-benchmark.md; reference/capsules/scientific-evaluation.md; reference/capsules/delivery.md; reference/field-catalog.md environment-lock/resource-snapshot; exact file bytes and versions are pinned by [source-baseline.json](../source-baseline.json). Locators above are relative to the supplied source/Architecture_Design package unless explicitly QA. |
| Inputs: fields, types, units, required/optional, validation | Accepted Brief and upstream stage artifacts, immutable captured baseline/validation resources, protected prepared package lock, pinned rubric/search scope and frozen hypothesis measurement/rule/repeat/seed constraints. Adopted type/version set: search-scope/screening-rubric/environment-lock/build-receipt/poc-artifact-bundle/execution-receipt/provisioning-receipt/research-report/gate-decision-index1; candidate-set/screening-result/opportunity-card/hypothesis-blueprint/poc-manifest/benchmark-payload/evaluation-verdict/delivery-manifest2; empirical-results2.0.0 native C002 amendment below |
| Outputs: fields, types, units, semantics, guarantees | Exact source-defined seven-stage artifact chain plus protected build/provision/execution/empirical receipts and final report/manifest; missing metrics retain explicit row status/reason under C002. |
| States and invariants | Pre-register science before POC; no baseline/data/measurement/rule drift, dependency discovery or empirical trial by Builder. Research Benchmark is code-only, baseline repeats precede treatment, measured network denied. Preserve all incoming idea IDs under M1-I004. Scientific verdict is independently recomputed; negative/inconclusive science stays deliverable. |
| Errors, timeout, retry, cancellation | No evidence/eligible idea, invalid bundle/lock/provisioning or failed baseline stops affected node. Treatment failure/missing metric uses source-defined unmeasured evidence, not invented values. Any aggregate/identity/source mismatch rejects. No auto repair/rebenchmark/replanning. |
| Side effects and idempotency | Protected environment preparation precedes execution; only frozen reviewed bytes install. Confined measured runs and actual outputs are retained; exactly-one Delivery exports authorized accepted content, without external publishing or side effects beyond declared authority. |
| Compatibility and migration | Existing source versions stay pinned except empirical-results2.0.0, explicitly versioned for user-approved C002. Never reinterpret an old missing row as an observation. Consumers adopt the C002 check amendments; declaration schema1.0.0 is unchanged. |
| Machine-readable schema / source path | [Critical schema catalog](../source/Architecture_Design/reference/catalog.json) and [field contracts](../source/Architecture_Design/reference/field-contracts.json), with referenced owning pages; generated implementation schemas are not created yet. Sidecar records use their owning benchmark-runner tables. |
| Provider/consumer verification responsibilities | Provider and consumer procedures are mapped to qualified V IDs in plan.md Verification Design. tasks.md owns their AC-to-work/evidence correspondence. No runtime PASS is established by design. |
| Open agreement questions | No unresolved product-intent question. Actual endpoint/credential/hardware/custody availability remains an execution prerequisite only for the paths that require it. Internal implementation/framing is selected in plan without widening this agreement. |

#### C002 native amendment: empirical-results:field-contract:2 / schema_version 2.0.0

The frozen source empirical-results:field-contract:1 remains preserved as input. This r1 agreement implements the user-approved per-run missing-data amendment as version 2.0.0; every consumer references M1-IF-005@r1 rather than silently treating the old contract as amended.

| Field | Required type and semantics |
| --- | --- |
| schema_version | Required string exactly 2.0.0. Other source root identity/runs fields retain their meaning; id remains empirical_results. |
| runs[].sequence | Required integer, exactly one row per actual execution-receipt sequence, contiguous ascending without gaps/duplicates. No row claims an unexecuted run. |
| runs[].status | Required enum measured, partial, unmeasured. measured means all registered metric IDs have admissible finite observations; partial means a nonempty proper subset does; unmeasured means none does. |
| runs[].metrics | Required map of registered metric_id to finite observed number, copied without rounding/filling/smoothing. Unknown IDs/duplicate log records reject. Failed execution does not promote printed numbers to admissible metrics; raw logs remain retained. |
| runs[].unmeasured_metrics | Required map of each other registered metric_id to its explicit source reason: run_failed, timeout, metric_not_emitted, non_finite_value or resource_limit_exceeded. It is empty for measured, nonempty for partial/unmeasured. |

For every row, metrics and unmeasured_metrics keys are disjoint and their union equals the blueprint metric set. Status must agree with the two maps. Receipt linkage and raw logs establish each value/reason. Sequence checks still cover every receipt run; finite-value checks apply to observed values and do not demand invented values for missing keys. raw_repeats_present requires every actual receipt run to have logs and an empirical row; only observed admissible values contribute to measured repeats, and incomplete metric sides retain the declared unmeasured reason/null aggregate and delta. Baseline/provisioning failure still halts without an accepted payload; partial failed candidate records and their rows remain retained, never presented as valid final artifacts. All other final protocol/repeat/baseline/receipt checks remain mandatory. Old v1 missing rows are never backfilled as observed data; any compatibility import must retain its original identity and limitations and cannot establish current C002 acceptance.

Consumed agreements: [M1-IF-001@r1](../M1-001/TASK.md#4-embedded-cross-module-agreements), [M1-IF-002@r2](../M1-002/TASK.md#4-embedded-cross-module-agreements), [M1-IF-003@r1](../M1-002/TASK.md#4-embedded-cross-module-agreements), [M1-IF-004@r1](../M1-003/TASK.md#4-embedded-cross-module-agreements).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-C002 / 2026-10-16 | User explicitly approved one empirical row per execution receipt run, including missing-metric status and reason | Empirical-results field contract and host checks; exact fields resolved in TASK agreement/spec/plan | No existing M1 evidence; supplied conflicting source remains preserved | Codex / approved user answer in this session |
| M1-C003 / 2026-10-16 | Invoked prompt supplies full-M1 snapshot and all-phases implementation plus separate four-case QA scope; supersedes earlier compiler-only assignment for this request | Current TASK scope and parent source allocation | Historical AI4R-001/DEVTOOLS results unchanged; no acceptance reused | Codex / current user request |
| M1-I004 / 2026-10-16 | Source-resolved implementation binding: Consolidation with identity preservation. Consolidation is one-pass normalization/grouping for assessment while every incoming idea_id remains an audit/scoring identity. Preserve materially different mechanisms/baselines/assumptions, per-ID citation membership and all dispositions. Do not invent replacement IDs, silently remove scoring rows, create duplicate-rejection eligibility or use reserved deferred dispositions. Source: PRD3.4.1-2; reference/capsules/screening.md scoring/ranking/coverage rules | Owning spec and IF r1; affected blocks/checks and work/evidence correspondence are mapped in plan.md/tasks.md | No prior M1 runtime evidence; consumers adopt this same canonical binding | Codex / source-specific reconciliation, not a fabricated new user approval |

Progress belongs in tasks.md when generated. Registration is not implementation, integration or verification.


### M1-I032 versioned scientific start/inspection consumer reconciliation

Research worker/host adapters consume owning001 IF001r2 before any source-declared shared/exclusive-resource parent starts. Whole-parent worker/reviewer membership, exact frozen admitted body/resource/lock/policy and actual fixed provisioning/Benchmark/Builder factory qualification remain mandatory. Host duties are distinct from source model tools; Benchmark zero model-call/tool limits cannot waive required host measurements or be borrowed for other calls. A current captured snapshot keeps its pins after later suspend/revoke. The canonical IF003r3 inspector provides original whole-attempt evidence only; native lease release additionally needs actual cessation. Unqualified old fresh science refuses. Valid scientific FAIL/INCONCLUSIVE remains distinct from missing infrastructure. No receipt, expected model output or mocked GPU is an actual positive.

The single field/behavior authorities are [M1-001 IF001r2](../M1-001/TASK.md#4-embedded-cross-module-agreements), [M1-002 IF003r3/IF016r2](../M1-002/TASK.md#4-embedded-cross-module-agreements). This consumer adds no parallel protocol fields, owning IF revision, public source field or authorization. Source allocation is TASKS I032; exact original sources: reference/declaration.md207-208/242-243; reference/run-plan.md97/138/460-542; research-benchmark14-30; Builder D45. Definitions may be prepared independently; dependent code follows current owner/neutral/consumer Analyze and independent RED, actual connected acceptance follows both implementations/resources.


2026-10-20 existing local Search technical refinement: TASK/plan r4, spec r3 unchanged, tasks r3. Install the actual Store-bound local-document connector and consume only the original bound scope, admitted declaration tool allowance and frozen accepted Compiler Brief. Exact source changes implement existing allocated Search and protected orchestration obligations without a public/schema/IF/AC change. Current evidence and C010 skipped checks remain in tasks.md; no runtime or whole-M1 acceptance follows.


2026-10-20 existing-function technical refinement: TASK r5, plan r5, tasks r4, unchanged spec r3. Owning004 captures fresh ordinary request/reference-document resources through the already allocated host intake boundary; original per-run bindings and exact source joins govern consumers. Owning001/007 optional router installation preserves fixed Codex and call-time integrity while supplying no unavailable API authority. Procedures and current source progress remain in registered native records. No public/source schema, interface identity, AC or work/check ID changes; C010 leaves current runtime acceptance NOT_RUN.

### M1-I033 host-input consumer definition under IF001r3

Existing host intake/capture and T013/T014 retain the original closed run-input-binding/local-document-buffer definitions above. Consume owner001 IF001r3 only through the common002 frozen-plan/native path. Owning004's reader proves the exact original run/account/workspace/submission/intake/upload order, buffer, original binding's base Ref and complete derived inventory recomputation. The finite parent-only query/result stays defined in001 IF001r3; no caller can select a base/derived inventory or extend its bounded original read list. Only original_request/local_document_buffer immutable input rows and inventory ID may differ; every other scientific/host resource, ref/availability/count, environment lock, permission/limit/configuration/policy remains exact. It never installs a native capability or treats preserved shapes as qualification.

Return the original qualified-intake Ref independently of document-loop variables; empty and nonempty documents retain the same original intake join. A fresh ordinary capture is distinct even with zero documents; duplicate/reconcile performs no recapture/replay. Finite/profile/private paths cannot use this operation to replace qualified pins. The actual installed001 resolver independently proves and constructs any exact per-original-run native mapping; Binder/Scheduler freeze that same derived Ref and keep strict equality. Existing IF005r1/artifact/source/API fields, scientific thresholds, FR/AC/work/check IDs and external defaults remain unchanged. No model/GPU/service/lease qualification is supplied; implementation and new runtime checks remain UNBUILT/NOT_RUN under C010 at this definition draft.


### M1-C019 current maintained-source integration

M1-C019 / 2026-10-21: Explicit user request: connect the complete maintained-design POC workflow to native web chat. Include qualified intake, Intent/Requirements compiler, accepted Research Brief, bounded DAG Planner, Search, Screening, Hypothesis, Builder/Benchmark POC, Evaluation and Delivery. Every work Capsule retains declared deterministic checks, independent verifier, mechanically validated assessment, protected gate and frozen routing. Current authority is docs/architecture/design-package/ and docs/product/received-prds/prd-m1-reviewed-2026-10-13.txt (SHA256 890c63ee4849d61e8c7ddc980891985d57c59005ca6c62be45957c59e82782de, 255245 bytes), replacing historical frozen-source allocation for this change. Existing evidence remains historical; direct chat is not workflow acceptance. Required focused boundary and connected-journey verification supersedes C010 only for this request; unrelated campaigns remain excluded. Owners: M1-001 startup/executor/model; M1-002 library/binder/gates/scheduler; M1-003 compiler; M1-004 research Capsules; M1-005 routing; M1-006 native web; M1-SYSTEM integration and current evidence. Admission bypasses, invented metrics and manufactured PASS records are prohibited.


### M1-C020 verifier disclosure decision

M1-C020 / 2026-10-21: Explicit user decision: semantic verification uses only pinned CC declaration and exact output content, with fixed input-independent instructions/criteria. Hide user input, original/reference documents, accepted predecessor content, producer conversation, policy/observations/review manifest and any reference-lookup capability from the semantic assessor. Preserve host deterministic source/identity checks, read-only independent verifier, mechanical assessment validation and protected committed gates. Do not claim hidden-input fidelity or external evidence verification. Input-aware versus output-only comparison is deferred; no automatic alternate mode. This supersedes C019's proposed input-aware verifier expansion, not the complete integrated POC workflow. Full and compact maintained design guard/compiler/reference/principle/decision records are synchronized. No declaration schema or existing IF payload revision changes: retain the existing declaration/output-only verifier boundary.
