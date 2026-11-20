# sf-001 specification
Revision 1; sources: latest user request (sections 1–6) and supplementary requirements 1–5; [TASK](TASK.md).

| AC | Required observable outcome | Verification |
| --- | --- | --- |
| AC-001 | Actual network acquisition of only niko1221/strata at recorded SHA; real source analysis maps loading, execution, routing/cache, CPU/GPU responsibilities | V01,V03 |
| AC-002 | Contract/available-artifact goal planning extracts stages from different parent workflows; two actual goals execute distinct paths | V01,V03 |
| AC-003 | Actual files and contents are checked; producer hashes/fields/shapes consumed by downstream, executable adaptations verified rather than field renaming | V01,V03 |
| AC-004 | Real dependency/build/validation failure updates recorded graph, inserts recovery, revalidates, retries; irreparable failure blocks consumers | V01,V03 |
| AC-005 | Factory-generated STRATA implementation builds and performs actual model inference on required native backend with comparison against original; source/local-tests/target-compilation/device-load/operator/model/comparison recorded separately | V03,V04 |
| AC-006 | Host UI displays only actual backend events/artifacts/commands/errors, can download/reopen them; startup/config and rerun records supplied | V02,V03 |
| AC-007 | Running factory extracts real production STRATA algorithm bodies and generates standalone src/strata_core.cpp, include/strata_core.h and CMakeLists.txt; compile/test succeed, Code Diff displays exact source, and downloadable huawei_native_strata.zip rebuilds without the upstream checkout | V01,V02,V03 |
| AC-008 | Post-construction Value Agent reports actual cross-workflow composition, artifact reuse, commands, source delivery and unresolved scope; model interpretation uses configured real provider or is explicitly unavailable without blocking source delivery | V01,V02,V03 |
| AC-009 | Fresh checkout opens the existing host Workflow page, selects packaged real recordings, replays actual task-driven internal-stage composition, opens exact generated source/Code Diff/build evidence, and downloads the same verified standalone ZIP without rerunning the factory | V02,V05 |
| AC-010 | The recorded pool contains executable subworkflows with multiple real children. Task/source/artifact contracts select individual children across different parents; unused siblings remain unexecuted. The UI shows the original parent paths, selected children, skipped siblings and the resulting cross-parent dependency chain, backed by frozen library definitions and actual selection/execution receipts | V01,V02,V03,V05 |

Completion requires every AC, particularly AC-005; source analysis, CPU tests, component build or baseline run cannot replace end-to-end target inference. Explicit missing resources remain BLOCKED. Tests may isolate services; production factory/UI cannot use synthetic success or timed DAG scripts.

AC-011 / V06: Both real workflow definitions and pinned donor CCs normalize into one validated pool, retaining executable entrypoints, hierarchy, port bindings, optionality, requirements, material paths/content identity and origin. Material-only CCs remain non-executable; duplicate identities, dangling references, invalid ports and composite cycles are rejected. No execution, implicit type conversion or runtime-success claim is introduced.

AC-012 / V07: Real STRATA and GoogleTest source acquisition fixes clean commits, exposes evidence and factory-owned Python/MD wrappers, and registers persistent versioned Workflow cards with independently executable named parts. UI reveals project-to-parts-to-definition registration and literal implementation/source bytes.

AC-013 / V07: An actual Agent reads Task Contract, MD policy and Library tool results, explains selected and omitted parts across Workflows, and proposes graph references/bindings. Deterministic admission checks exact versions, named content contracts, dependency acyclicity and requested deliverables. Two task contracts must yield different actual model-selected plans before live dynamic planning is accepted; test drivers do not count.

AC-014 / V07: Real Python and Agent-MD execution preserve invocation logs, owned hash-checked artifacts and downstream consumption receipts. Failures block dependent work. Saved jobs reopen by read-only links without execution. Source/CPU output cannot establish native compilation, device use or full inference. Live model-dependent acceptance remains incomplete until authenticated calls and actual generated test execution pass.

AC-015 / V08. Browse each pinned project's production functions with original implementation and data handoff. Partition every tracked path exactly once. Reconstruct both original source trees from the module manifests and record the original targets built from the reconstructed trees. The offline replay identifies the parts used for the specific STRATA construction run.
AC-016 / V09. The existing host Workflow entry submits a new structured task, records source preparation and typed selection, streams actual execution events, and opens the newly generated Product. Routing-only and routing/activation/aggregation requests select different task graphs and yield distinct buildable source projects. Reloading a run reopens its own evidence. The guided example remains read-only. Native device and full-model acceptance retain their separate requirements.

AC-017 / V09. Plan and execute a task over registered Library contracts independently of the STRATA construction recipe. Retain the existing Agent proposal path and the host authority boundary. A non-construction task publishes its requested output through the same executor and owned artifact interface.

AC-018 / V10. The Scheduler parses the admitted Task Graph JSON, validates graph and pinned contracts, and assigns an execution method and reason to every node before Construction. It shares M1's dependency checks and releases each node only after its required predecessors verify. Failed producers block consumers. Registered Agent nodes retain their instruction, model and artifact checks. The host shows Scheduling between Compose and Construction from the same Task Graph bytes and recorded assignments.
