# sf-001 — real Software Factory and STRATA engineering
Revision 1, 2026-11-13. Parent: [TASKS](../TASKS.md). Executor: Codex; delegated backend, STRATA engineering, frontend and resource audit.
Baseline: existing AI4Research-Main @ 141c1c401138f916af0a41aca791adf226d814c7 plus preserved prior frontend changes. User explicitly supersedes mock/demo scope and authorizes real source acquisition, implementation, process execution and dynamic stage composition. The initial scope did not authorize publication; the later branch-publication instruction below supersedes that boundary for the requested GitHub branch.

## Registry
[spec](spec.md) owns acceptance; [plan](plan.md) owns blocks/checks; [tasks](tasks.md) owns progress and current evidence. Evidence remains under evidence/ and actual per-run artifact directories. No separate approval/checklist is introduced.

## Scope
Reuse existing host Sidebar/Layout and research artifact/contract practices where compatible. Add factory service with cross-workflow microstage planning, actual artifact validation, bounded process execution, dynamic recovery, persistent revisions/events and artifact downloads. Execute actual STRATA engineering, build, inference and comparison. Native Ascend target remains required; missing resources block only dependent steps, not other work. CPU checks do not establish Ascend or full inference.

## sf-if-001@r1: factory UI/API boundary
GET /api/v1/factory/catalog returns groups/subworkflows/stages with entrypoint, ports, tools, environment and verifier. POST /api/v1/factory/runs accepts goals (artifact kinds), exact target repository, optional pinned revision/model path, target_backend and bounded options. Snapshot exposes nodes/attempts/commands/inputs/outputs/errors/verification, edges, immutable artifact identities, graph revisions and sequence. Events are sequenced real observations. Downloads resolve published artifact IDs only within owned run roots. Errors/blocked states never become success merely by skipping a stage. Local access requires loopback/same-origin; protected host mode retains native authority and ownership. No user-provided arbitrary command field.
Provider: backend engine/API; consumer: integrated Workflow UI and CLI. Verification: V01–V03. No model API substitute and no production synthetic events.

## Changes/unresolved inputs
Uploaded ZIP cannot currently be inspected due tool size limit. Work proceeds on current worktree as user permits. Actual Ascend access, SDK/toolchain and model remain unresolved until resource audit proves them available. Their absence must remain explicit at dependent acceptance layers.

## Latest explicit construction pipeline
Current user additionally requested real CUDA declaration extraction, a real SchemaMismatchError, subprocess metadata adapter, actual generated C++/CMake/Make/ELF execution and SSE terminal. These are implemented in construction_pipeline.py/scripts/adapters and verified by real run; descriptor-format conversion is explicitly not a semantic CUDA→Ascend implementation. Source/local/component results remain separate from native/model acceptance.

## Source-product construction revision — 2026-11-14
User requires the running factory itself to extract real production algorithm bodies and generate a standalone C++ source project, specifically src/strata_core.cpp, include/strata_core.h and CMakeLists.txt, with actual compilation, arithmetic validation, source Code Diff and huawei_native_strata.zip delivery. Replace test-harness copying in the construction path; the adapter must produce source-bound semantic input for code generation. Planned lowering is an ordinary producer/consumer contract, not a deliberate schema-error demonstration. The generated CPU core is an incremental product; full-model/native acceptance above remains required and incomplete.

sf-if-001@r2 adds construction.code_diff with schema strata.code.diff.v1 and files [{source_path, generated_path, source_code, generated_code}], and construction.package as the built/tested standalone source ZIP. The existing owner-checked artifact route transports both. Prior V03 construction evidence is historical and cannot verify this changed generator.

User also requests a Value AI Agent after construction. Its executable assessment stage consumes the actual source/build-validation/package artifacts, observes all main-goal outcomes after they settle, and emits value.report plus value.evidence. Recorded metrics and citations are authoritative; optional configured-model interpretation retains its own invocation/provenance status. Model unavailability must not be disguised as AI output or suppress the generated source package.

## Automatic independent audit / implementation loop — 2026-11-14
User requires every audit deviation to produce concrete modification requirements and enter implementation immediately, followed by independent re-audit until alignment. Baseline audit and R1–R9 requirements are fixed at `/workspace/software-factory-delivery/independent-audit/report.md`; cycle-two review is `report-cycle2.md`. These are independent findings, not approval records. Continue the same registered task; no new permission gate, alternate demo or retrospective success rewrite.

Required corrections: R1 generated source must feed the full candidate; R2 task/acceptance and real source features select implementation stages; R3 mathematical code is source-lowered with per-operation semantic verification; R4 reference/candidate backend roles are distinct; R5 real executable hierarchy, instances and output ports preserve identity; R6 graph colors reflect actual input receipts; R7 each run fixes executor/catalog/source recipes; R8 full native/model graph and layered target acceptance remain mandatory; R9 AI value interpretation requires a real configured provider call. Hardware/model/provider absence does not close software gaps or downgrade acceptance.

Cycle-two follow-ups are C2-1 per-operation oracle coverage (mixed known/unknown cannot borrow another operation's comparisons), C2-2 same-kind multi-output port custody, C2-3 runtime child artifact consumption receipts and C2-4 actual public parent-workflow execution. Each requires a new candidate/evidence; prior immutable runs are not edited.

## Recorded replay and branch publication — 2026-11-14
User requests replay of the existing code-production workflow without rerunning it. The integrated viewer and portable export must consume the recorded event prefix, expose code and artifacts only after publication, and retain actual graph revisions and command logs. No replay action may construct a new run.

User explicitly authorizes creating and pushing `dynamical-workflow` to `Stellven/jiuwenswarm`, including the completed implementation, generated source projects, and a concise manager update. Publication excludes credentials, machine inventories, runtime logs unrelated to evidence, caches and model files. The manager update presents completed constructive work; technical acceptance records remain intact.

## Monday full-flow demonstration revision
User authorizes implementing and verifying the complete presentation journey: submit the real STRATA repository and Huawei Native / Ascend goal; inspect source/task-driven cross-workflow internal-stage composition; inspect actual generated C++ under `src/`; inspect build/numerical evidence; obtain the source engineering package; compare a second task's genuinely different recorded execution path. Existing recorded playback is permitted, and new execution is permitted where needed for changed code verification. Previous immutable recordings must retain their original task, backend, owner, timestamps and results.

The integrated existing host UI remains the only product interface. Add portable authenticated read-only recordings and a local launcher so a fresh checkout can show real historical production without original absolute filesystem paths or a new run. Show new Ascend requests separately from historical CPU source-construction records. Native source generation must fail closed on missing coverage and must never count CPU arithmetic as Ascend device/model validation. External resource prerequisites retain their original acceptance requirements.

sf-if-001@r3 adds GET `/api/v1/factory/recordings` (owned recording summaries), GET `/recordings/{id}` (exact recorded run, events, catalog, provenance, `read_only:true`) and GET `/recordings/{id}/artifacts/{artifact_id}` (verified published bytes). Portable bundles preserve original metadata/paths and resolve byte storage via validated immutable path mappings; replay cannot dispatch stages. Existing live-run API remains unchanged.

## Partial internal-stage selection and new recording

The user clarified that reusable parents must themselves contain multiple executable internal stages: extract selected children across existing subworkflows, rather than selecting whole atomic parents. AC-010 records this requirement. A recorded full library, typed parent bindings, exact full-reference origins and actual selection receipts must establish both selected and skipped children. Canonical stage identity alone cannot identify the selected parent.

The user explicitly authorized one background native-source/CPU-reference production recording; the audit/fix/verification loop corrected its discovered singleton-parent deficiency and retained both immutable executions. The Monday primary is corrected run `11a6ce02166b4618baea6db59aaf44ec`. Onsite presentation remains read-only replay. No local NPU/SDK/model attempt is authorized by this source-only run, and no such attempt is required for playback.

sf-if-001@r3 additionally exposes bounded GET `/recordings/{id}/replay?after=N&speed=1|4|16&until=M`. SSE `recorded` frames contain exact original event JSON bytes; pacing happens on the backend, ends at the original bounded sequence, and cancellation stops delivery. It cannot dispatch execution. The recording includes its original complete workflow library and actual origin/selection receipts; historical recordings lacking these cannot acquire a later library retrospectively.

## Shared capability pool schema — agreed integration Task 1
User agrees to normalize existing workflow/subworkflow/stage definitions and donor CC declarations into one pool, followed separately by a Run Coordinator. Task 1 introduces a reviewable v0.1 shared declaration schema, non-executing adapters, actual pinned-source examples and validation. It does not merge donor architecture or change either executor. Preserve original declarations, binding semantics, port transport, materials, requirements and immutable provenance. Unknown contracts remain unknown; normalization grants no authority and establishes no computational compatibility.

sf-if-002@draft-0.1: shared capability pool document. Provider: workflow and CC normalizers. Consumer: future Run Coordinator and pool UI. Owning schema: `jiuwenswarm/software_factory/schemas/capability-pool.schema.json`.

## Executable Workflow Library and Agent Composer — 2026-11-19

The user authorizes implementation of a visible real two-project onboarding, versioned Library, Agent Planner, admitted Task Graph and actual execution. STRATA and GoogleTest are acquired at resolved clean commits. Factory-owned wrappers and MD instructions are distinguished from upstream declarations. Existing host layout/replay and native/model acceptance remain intact.

sf-if-003@r1: `/api/v1/factory/library` serves immutable Workflow definitions. `/import` acquires real source, decomposes it and registers wrappers; `/policy` exposes the actual composer MD; `/source` reads confined source/instruction bytes; `/plan` invokes a real restricted Agent using Task Contract, policy and Library tools; `/execute` accepts only an owned admitted plan. Owned imports/plans/executions expose persisted snapshots and sequenced SSE events; `/artifacts/{run}/{id}` serves published hash-checked bytes. Library definitions contain fixed source/code/prompt versions and named content contracts. Graph nodes contain definition references, parameters and producer/port bindings. Runtime attempts, processes and artifacts are separate records. Python entrypoints and Agent-executed MD share the file contract; instruction text alone never passes a node. Arbitrary model-proposed shell commands/paths are not executable graph definitions.

The offline Library also presents the production functions of the pinned STRATA and GoogleTest repositories and retains a complete partition of their tracked source files. Reassembling all source packages must recover the pinned project tree, with compiled targets recorded from that recovered source. Only parts with executable definitions can enter the task's runtime graph.

Actual model-service authentication is a dependency. A failed real invocation remains blocked with logs; isolated test drivers cannot establish live Agent planning or Prompt execution. Missing Ascend/CANN/model resources continue to block the original target acceptance only, without halting independent implementation.

## Supervisor review iterations — 2026-11-19

Run at least five independent review rounds against the working candidate, using the operator's supervisor simulation prompt. Start with whether an unfamiliar viewer can point to the current input, action, resulting object, and its relationship to the request. Keep actual commands, definitions, bindings, and source files available for progressively deeper questions. Each round can challenge presentation order, wording, or usefulness even when the implementation behaves correctly. Fix reproducible defects in the product, address comprehension barriers in the walkthrough, and record broader challenges with their evidence and dependencies. The review does not authorize changes to frozen M1 boundaries or promotion of blocked native and live-Agent acceptance.
## Host live workflow and guided example

The `dynamical-workflow` branch integrates project extraction, the Library, Composer, execution and Product into the existing host Workflow route. The Library supports both contract-based and Agent planning. The STRATA build submits a new engineering task using pinned-source preparation, the shared contract planner, graph admission and WorkflowExecutor. Factory build actions have a separate registry from imported project workflows. The host serves the saved guided example alongside live workflows.

sf-if-003@r2 exposes owner-checked `POST /library/build`, `GET /library/builds`, `GET /library/builds/{id}`, and the corresponding `/stream` and `/product` endpoints under `/api/v1/factory`. The read-only `GET /api/v1/factory/guided-replay` presents a packaged, earlier verified run. A current Product is derived from that job's actual execution artifacts after its run verifies.

## Scheduler and Builder dispatch

The Scheduler reads the admitted Task Graph JSON, records the received bytes, and assigns an execution method to each pinned node before releasing work. A Builder runs Python/tool code or invokes a restricted Agent according to the pinned implementation. Work is released only after required predecessors verify. The Factory and protected M1 research Scheduler share predecessor gating, and the Factory uses the M1 graph check. M1 research plans keep their own frozen authority and native execution boundary. The host presents Scheduling between Compose and Construction from the actual input receipt and assignment events.
