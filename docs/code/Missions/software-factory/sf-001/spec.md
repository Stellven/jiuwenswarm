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
