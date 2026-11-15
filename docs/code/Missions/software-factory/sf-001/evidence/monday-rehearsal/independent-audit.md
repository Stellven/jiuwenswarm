# Monday independent audit — corrected production and actual host rehearsal

Audit date: 2026-11-15 UTC. Reviewer: independent audit agent, read-only for product/runtime code. No factory execution was dispatched by this audit. This report is the only file written by the auditor.

**Verdict: PASS for the explicitly scoped demonstration of real inner-stage composition, Ascend/CANN source production, and separate CPU reference build/numerical validation. Full native/model acceptance AC-005 remains NOT_COMPLETE.** The presentation now explains the actual work, rather than relying on a workflow illustration. The final manager screenshots need no further product correction for this scope.

## What the manager can understand from the actual host

| Question | Independent judgement | Actual host evidence |
|---|---|---|
| What was submitted? | Clear. The pinned STRATA CUDA repository, routing/activation/aggregation requirements, target ASCEND, source-generation acceptance and separate CPU checks are visible. The request explicitly excludes native compilation, device execution and model execution from this run. | [Task and existing pool](01-task-and-existing-pool.png) |
| Which existing inner stages were selected? | Clear. The frozen pool contains real multi-child subworkflows. Extract is selected while its Discover sibling remains unselected; scalar/cooperative Lower are selected while their local Extract siblings remain unselected. Highlighting uses full references, so a stage with the same canonical ID in another parent is not falsely selected. | [Selected inner stages](02-extracted-inner-stages.png) |
| How do they form a new chain? | Clear. Composition shows source extraction, implementation lowering and composition with their actual parent origins and artifact handoffs. The new chain is backed by executed nodes and receipts. | [Composition](02-extracted-inner-stages.png) |
| What was really delivered and checked? | Clear. Source shows the published CANN algorithm; Diff shows original CUDA beside generated Ascend C++; Run log exposes actual commands/PIDs/results; Downloads provides the source ZIP. CPU352 and native/model non-validation are distinguished. | [CANN C++](03-real-ascend-cpp.png), [actual Diff](04-cuda-to-ascend-diff.png), [process and stdout](05b-real-cpu-process-output.png), [validation scope](06b-native-validation-scope.png), [download](07-delivered-source-project.png) |

The refreshed Diff capture contains loaded source bytes. The refreshed process capture visibly contains child PID **25114**, exit **0**, duration and literal CPU output with **352** comparisons. The native-scope capture visibly shows `full_inference_validated=false`; the request header also states that native compilation, device and model execution were not requested.

The saved actual-browser rehearsal records 11 checks, 12 GET requests and no page errors. It exercises the actual host deep link, event-bounded backend replay, exact source downloads and rewind. It records no POST, live-run event stream or factory dispatch. See [results.json](results.json).

## Primary production identity and custody

- Actual run: [`11a6ce02166b4618baea6db59aaf44ec`](../../../recordings/ascend-inner-stages.zip), completed, **15 nodes / 132 events / 54 published artifacts**.
- Requested goals: `construction.native_sources` and `construction.cpu_validation`; both have real verified goal receipts. Target: `ascend`.
- Pinned upstream revision: `13eedf552417a6a791a7d13c6597e24300ee3a09`.
- Producer recipe digest: `39f995bc4d2be218f8c0ab4e9a27fb1e058c4f75f6995dba0f631704ee29b8fd`.
- Frozen workflow library SHA-256: `c3e5a4c28656f2b8be1176964b4e05971efef8d82972461f57e060541cda2a1c`.
- Published native source ZIP SHA-256: `30c509c862799b14cf5e80aea6c291ee653f7f574d004ca92316f2fceae07449`; **40,239 bytes / 27 source files**.
- Portable primary replay: [ascend-inner-stages.zip](../../../recordings/ascend-inner-stages.zip).

Independent artifact checks validated all 54 published hashes, all 27 ZIP member bytes against the source manifest, and 20 downstream artifact-consumption records against their producer outputs and graph edges. The standalone native C++ artifact matches its ZIP member. All six Diff pairs (three CPU and three Ascend) contain generated code present in the delivered source files; the original bodies/hashes resolve to the pinned upstream source. The three selected CPU lowered implementations occur in the delivered CPU C++.

The ZIP contains actual `src/ascend/router.cpp`, `src/ascend/swiglu.cpp`, `src/ascend/moe_combine.cpp`, `src/strata_native.cpp`, CMake/runtime headers, CPU reference, numerical tests, source references and provenance. The Ascend CMake branch excludes CPU core source objects. This is source inspection, not evidence of a successful native compile.

## Inner-subworkflow selection is real after the correction

The earlier source-production record `528acf3c90ff4d7c95e67d4fcff15c01` generated real source and validated CPU output, but its singleton wrappers did **not** demonstrate selection inside an existing multi-child subworkflow. That was a substantive runtime gap. It was corrected in registry, planner and engine, followed by the new primary production above; the earlier record remains an explicitly pre-fix archive.

The primary run freezes **16 workflows / 26 subworkflows**, including three real two-child subworkflows. Whole-parent execution and leaf execution have meaningful separate behavior; their children are executable stages, not presentation labels.

| Actual selected child | Executed instances | Actual unselected sibling in that same parent |
|---|---|---|
| `function_extraction/function_extraction/extract` | n9, n11, n13 | `function_extraction/function_extraction/discover` |
| `cooperative_implementation/cooperative_lowering/lower` | n10 | `cooperative_implementation/cooperative_lowering/extract` |
| `scalar_implementation/scalar_lowering/lower` | n12, n14 | `scalar_implementation/scalar_lowering/extract` |

All six calls have actual `workflow.expanded` events, exact selection scope, frozen parent-definition hashes, full-reference origins and bound published inputs. None of the skipped full references appears in the executed node set. Discovery legitimately runs under `source_acquisition/semantic_discovery/discover`; this is a different parent reference. Every one of the 15 executed nodes has a full-reference origin.

The extractor consumes already published operation inventory; lowerers consume the actual extracted operator artifacts. Origin identity is included in node instance identity, preventing a shared canonical StageID from replacing another parent's receipt. This supports partial reuse and cross-parent composition, rather than replaying entire parent workflows.

## Replay and graph truth

Independent projection checked every one of the **133** primary prefix states. All eight node-set/order transitions coincide with original `graph.updated` events; no prefix has a dangling edge; final node order/status matches the persisted run. Outputs and source visibility are restricted to their actual publication prefix.

An independent ASGI replay check used a service guard that rejects any live factory access. All **132 raw historical JSONL event lines and event IDs** matched exactly, with actual 16x timestamp pacing; native source/manifest/ZIP and CPU-report downloads matched their published hashes. Separate bounded-cursor checks returned only the original requested event interval, without a synthetic terminal event. Current workflow frontend and offline fallback have no frontend graph clock; automatic replay timing comes from backend SSE, while offline fallback is manual.

The workflow library is captured inline and as a hashed recipe file. Reader validation checks typed bindings, parent/child references, selection scope, graph expansion and origins against that frozen library. The final reader-only hardening rejects stripping expansion events or origins from partial selections. That reader change is separate from the immutable producer recipe; historical source snapshots and artifacts were not rewritten.

The three legacy core/normalization/mixed recordings independently establish that the same historical pool and recipe produce different selected graphs for different requirements. They retain their original CPU scope and older library structure. They do not prove that three different tasks ran against the corrected multi-child library; the primary corrected record proves the inner-stage composition for its recorded task.

## Build and numerical evidence, with its limits

The primary run has **16 command records / 15 real child PIDs**, including actual source acquisition, analysis, generation, toolchain recovery, CMake/build and numerical validation. The initial missing-CMake spawn failure has exit 127 and no fabricated PID. A real dependency-recovery stage and subsequent successful retry remain in the history. Recorded factory worker PID **24787** is explicitly distinguished from child process PIDs; in-process Python stages do not claim separate subprocesses.

The actual built CPU reference reports backend **CPU**, complete operation coverage, and **352** comparisons: **284 router + 51 activation + 17 combine**. Build/execution manifests hash the actual ELF outputs. No Ascend CMake configuration, NPU device call, model execution or original-model comparison occurred in this source-only record.

Independent review also checked the separately recorded detached ZIP QA: 27 unpacked source files match the published ZIP; fresh CPU configure/build/CTest succeeded, with CPU352 in the saved test log. Its [rebuild.json](detached-source-rebuild/rebuild.json) explicitly labels this **external artifact QA, not an original factory stage**. It does not add a stage to the original trace or establish a native rebuild.

Saved verification logs reviewed include the 133-test backend suite, meaningful whole-parent/leaf production-pool tests, final reader tamper tests, frontend scoped tests/production build and launcher asset-integrity checks. These checks validate their stated software boundaries. They do not certify CANN compilation or device/model correctness.

## Remaining acceptance boundary

| Layer | Supported conclusion |
|---|---|
| Existing multi-child inner-stage selection and composition | PASS in the corrected actual production. |
| Real pinned-source extraction, published CANN source and source ZIP | PASS for the supported routing/activation/aggregation forms. |
| CPU reference compilation and numerical checks | PASS, 352 comparisons; detached CPU source-package rebuild also passes. |
| Native compilation | NOT_RUN. |
| Native device numerical equivalence | NOT_RUN. |
| Full model inference and original-model comparison | NOT_RUN; AC-005 remains NOT_COMPLETE. |

The native generator implements bounded, reviewed source-contract ports for known computational forms; it is not an arbitrary-source native compiler. Candidate CANN FP32 paths also require actual device equivalence checks against reference behavior. Full native runtime/model integration remains a software delivery gap as well as requiring CANN, device and model resources. The correct Monday claim is therefore **real dynamic inner-stage construction producing Ascend source, with independently validated CPU reference**, not completed native model inference.

No further factory execution is required for this replay presentation. Any later native compilation/device/model acceptance needs its own explicit scope and actual recorded evidence.

Repository publication note: local links were relocated; the run link opens the portable bundle containing the exact original run JSON. Audit findings are unchanged.
