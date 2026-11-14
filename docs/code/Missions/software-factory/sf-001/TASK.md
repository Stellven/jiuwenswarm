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
