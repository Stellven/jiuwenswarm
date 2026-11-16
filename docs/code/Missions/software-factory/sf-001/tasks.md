# sf-001 progress
Revision 1. User source is registered in TASK/spec; this is the only current work matrix.
- [x] T001 Inspect existing source and historical demo evidence, register superseding scope.
- [x] T002 Implement B01 real dynamic executor and contract/artifact checks.
- [x] T003 Implement and execute B02 source-bound expert candidate/component construction; full native model implementation remains open under T006.
- [x] T004 Implement B03 host API and live UI.
- [x] T005 Run V01–03 and retain exact inputs, hashes, commands and actual results.
- [ ] T006 Run V04 native model inference/comparison after resources actually become available.

| Acceptance | Blocks | Required check | Current result / evidence |
| --- | --- | --- | --- |
| AC-001 | B02 | V01,V03 | PASS: fixed real source, module/hash evidence; RUN-001 |
| AC-002 | B01 | V01,V03 | PASS: 19-node construction vs 2-node analysis actual runs; RUN-001 |
| AC-003 | B01,B02 | V01,V03 | PARTIAL: real inventory/data/parity checks pass; full native algorithm/weights migration not established |
| AC-004 | B01,B02 | V01,V03 | PASS: actual schema failure, subprocess adapter, producer rebind, attempts and 5 graph revisions; RUN-001 |
| AC-005 | B02 | V03,V04 | BLOCKED: local Ascend SDK/device/model unavailable; remote resource audit ongoing |
| AC-006 | B03 | V02,V03 | PASS for actual factory API + host frontend SSE/artifact paths; RUN-001 |

Conclusion: NOT_COMPLETE. Earlier demo acceptance cannot establish factory or STRATA acceptance. Runtime source/config changes invalidate affected checks; prior runs remain historical.

Current execution evidence: [RUN-001](evidence/RUN-001.md), [proof](evidence/proof.json), [source hashes](evidence/source-manifest.json). Overall NOT COMPLETE: AC-003 partial, AC-005/T006 blocked and required full native compute implementation unfinished. CPU component success is not full STRATA reproduction.

- [x] T007 Replace construction test-copy path with source-driven semantic extraction and standalone production C++ generation; build, validate, display actual Code Diff and package/rebuild source ZIP (AC-007). New source construction evidence: [RUN-002](evidence/RUN-002.md). Native/model inference remains incomplete.
- [x] T008 Add deferred Value Agent evidence/report stage, actual source/ZIP validation and consumed-versus-planned edge accounting (AC-008). Real provider assessment remains NOT_RUN: openjiuwen/ruamel unavailable. Deterministic report explicitly identifies that limitation.

Current effective construction evidence is RUN-002; RUN-001 remains historical. AC-007 source/build/rebuild and UI transport are verified. AC-008 evidence/report mechanics are verified, AI invocation is unavailable. AC-003 remains partial and AC-005 remains incomplete; this is not full STRATA reproduction.

## Current audit-driven candidate

RUN-002 and prior UI/build checks are historical for the old generator. The independent audit classified that candidate PARTIAL; the new candidate requires new evidence before any overall acceptance. User has authorized an automatic implement → run → independent audit loop.

| Requirement | Modification / current verification |
| --- | --- |
| R1 | `candidate.integrate_generated` consumes actual generated source, changes full candidate callsites/CMake and validates a real host bridge. CUDA capture transport has isolated tests only; native/full execution is not passed. |
| R2 | Formal task/acceptance contract, actual operation discovery and runtime implementation-stage composition. Same-goal real network runs e20cd5bb89a34dcba385a696596119e7 and 475135502cfe45d4972f8d6da1b1f4d5 selected three versus one implementation instances. New receipt/oracle changes require fresh runs. |
| R3 / C2-1 | General source-body lowering replaced fixed function names/body hashes/route templates. Per-source operation coverage plus explicit bounded numeric task oracle is being connected to executable validation and the standalone ZIP. Unknown operations cannot borrow known comparison counts. |
| R4 | Original CUDA reference separated from candidate target; role/configuration contract tests pass. Real cross-device model comparison remains blocked. |
| R5 / C2-2 | Executable parent/subworkflow/stage registry, public workflow selection, instance-sensitive bindings and same-kind output port custody. Three real-file/process port regressions pass; public parent selection still needs a production run. |
| R6 / C2-3 | UI colors follow actual downstream input/publication receipts; historical details use the displayed snapshot. Runtime child-consumption receipt recording added, targeted 20 checks passed; fresh production receipt/UI evidence pending. |
| R7 | Per-run source/catalog/request recipe snapshots and command code/executable hashes; source changes fail closed. Six provenance checks pass; fresh production recipe data retained in actual runs. |
| R8 | UNFINISHED: complete native mathematical/runtime graph, SDK/device/model, native compile/load/operators/model/original comparison. CPU and isolated CUDA transport tests do not close this. |
| R9 | UNAVAILABLE: actual default provider/model/base/auth are unconfigured, and native model runtime dependencies absent. Deterministic reports remain explicitly identified; no AI invocation claimed. |

Cycle-two broad backend run: 70 tests, one outdated hierarchy expectation failed (source acquisition now includes actual discovery). It was corrected and 20 focused checks passed. A complete final same-version run and independent re-audit remain required. Do not infer PASS from code presence or these work records.

## Cycle-three verified checkpoint (overall NOT_COMPLETE)

Independent report: `/workspace/software-factory-delivery/independent-audit/report-cycle3.md`; original evidence remains immutable. C2-1–C2-4 are fixed and independently verified within the selected CPU source-construction scope. Full same-version backend suite: **81 passed**, 290.566s, `audit/factory-tests-cycle3.log`. UI: 18 isolated checks/build plus actual source/graph/ZIP/report/receipt/history audits passed. These do not establish native/model success.

Eight actual network-backed cases share recipe digest `29da76161cef3dd019d2b2d3c06fdc3650d6170b986017827b4711dc9fbe4cea`:

| Case | Run | Actual result |
| --- | --- | --- |
| Core construction | 6db7a2b968c8434eaa9a508a6d16a7cf | completed; three source-selected lowering instances |
| Normalization | 02446be989844a3fb7e43dc9bd6a8e0a | completed; one source-selected lowering instance; same goals as core |
| Mixed known/new operator | b152d434c8e14b01adc8c4aa40ad83f2 | completed; per-source built-in plus external oracle; ZIP independent CTest2/2 |
| Native/full-model requirements | baf3d77a8301423180ccda45fb11c66b | blocked; generated candidate integrated; native math/runtime and environment/model incomplete |
| Public parent workflow | 9e4d7d2016844066b504d87bc712b06c | completed; wrapper + fetch + scan + discover |
| Missing oracle | 68c1f757248741c6b14d0bcf7a3fc978 | blocked; unverified scalar cannot borrow router comparison counts; no package |
| Wrong oracle | 0121a742659c402eb9efc66265502573 | failed; actual numerical mismatch; no package |
| Public internal stage | cab4cb9235184b8d9b45c1ef40825589 | completed; wrapper + required fetch + scan; no discovery sibling replay |

Versioned delivery is `/workspace/software-factory-delivery/cycle3/`, including actual source ZIPs, extracted C++ sources, operation validation, portability evidence and current factory source overlay. Previous stable package/source paths remain historical; they were not overwritten to imply updated evidence.

R8 remains UNFINISHED: full native mathematical/runtime implementation as well as actual target compile/load/operators/model/original comparison. R9 remains UNAVAILABLE: no configured real model provider plus missing model runtime dependencies. Exact Ascend chip/CANN/model architecture+pack and authorized model-provider configuration have been requested asynchronously; no elapsed-time approval or fabricated results are inferred. The task is not closed.

## Read-only recorded replay and publication checkpoint

- [x] T009 Integrate prefix-only recorded playback: play/pause, pointer seek, event/stage stepping, and 1x/4x/16x. Replay exposes only recorded nodes, attempts, commands and published artifacts; rewinding removes future content. Construction and live SSE are disabled in replay mode.
- [x] T010 Export three self-contained HTML replays from existing immutable runs, with terminal, source Code Diff and source ZIP download. Shared artifact-receipt validation governs edge colors in both viewers.
- [x] T011 Assemble the `dynamical-workflow` branch: executable factory sources, integrated frontend, standalone generated C++ projects, replays, technical records and concise manager update. Publication excludes machine inventories, credentials and unrelated runtime logs.

Replay checks: 16 prefix/receipt regressions, 8 offline export checks and 18 existing UI/client checks passed. Main frontend build passed (31.23s). Browser verification exercised eight existing runs with zero factory mutations, zero replay SSE connections and zero browser errors. Offline HTML verification observed zero network requests and errors, including actual recorded failure/retry edge transitions. No workflow, source clone, C++ construction or inference was rerun for replay.

Evidence: [integrated replay](evidence/integrated-replay/results.json), [offline replay](evidence/publication/offline-replay-browser.json), [export tests](evidence/publication/replay-export-tests.txt), [projection tests](evidence/publication/replay-projection-tests.txt), [frontend build](evidence/publication/frontend-replay-build.txt). The archived source projects and ZIPs retain their exact recorded bytes.

## Monday complete presentation implementation

- [x] T012 Portable verified historical recording bundles + owner-checked read-only API; fresh-checkout data path.
- [x] T013 Integrated minimal full-flow UI: task, stage hierarchy/lineage, dynamic graph, source/Code Diff/build/verification/artifacts, real recording comparison.
- [x] T014 One-command launcher and complete recorded rehearsal against the existing built host UI.
- [x] T015 Correct source-only native core generation and backend evidence separation; source-bound routing, activation and aggregation CANN implementations. Target compilation, device execution and the complete model remain under unfinished T006/R8.
- [x] T016 Same-candidate checks and independent manager-view audit; corrected capture timing/scroll evidence and rechecked the actual host. Source-production demonstration PASS; full AC-005 remains NOT_COMPLETE.
- [x] T017 Replace singleton-only extraction evidence with executable multi-child parents, typed partial imports, frozen library and recorded selected/skipped siblings (AC-010).

Historical recordings remain immutable. New code changes require new tests/evidence for affected behavior; recorded CPU completion cannot close native target acceptance.

## Corrected Monday source-production candidate

Primary real run: `11a6ce02166b4618baea6db59aaf44ec`, completed **132 events, 15 nodes, 54 artifacts**. Fixed STRATA source: `13eedf552417a6a791a7d13c6597e24300ee3a09`. Frozen workflow library SHA-256: `c3e5a4c28656f2b8be1176964b4e05971efef8d82972461f57e060541cda2a1c`.

Three real multi-child subworkflows establish the required granularity: function extraction has `discover → extract`; scalar and cooperative implementation each have `extract → lower`. Six actual partial imports select only extraction's `extract` and implementation's `lower` for three source operations; their own unused siblings are not executed. Source-derived cooperative versus scalar contracts select different implementation parents. Full refs and parent hashes distinguish reused canonical stages. The complete original definitions, import receipts, execution entrypoints and consumed files are retained in `recordings/ascend-inner-stages.zip`.

Actual generated CANN math is delivered in `deliverables/ascend-source/source/src/ascend/{router,swiglu,moe_combine}.cpp`, with runtime header, CPU reference, build scripts and tests. The 27-file source package SHA-256 is `30c509c862799b14cf5e80aea6c291ee653f7f574d004ca92316f2fceae07449`. Factory CPU validation performed **352 comparisons** (routing 284, activation 51, aggregation 17). A separate detached ZIP rebuild and CTest also passed; that QA is explicitly outside the original factory timeline and never inserted into its 132 events.

| Acceptance slice | Current evidence | Result |
| --- | --- | --- |
| AC-002/AC-010 partial internal-stage construction | Actual six partial imports, frozen multi-child registry, consumed artifacts and recorded graph | PASS for source-production scope |
| AC-003 selected source operations | 20 input/edge receipts; exact source/ZIP/diff bytes; actual CPU comparisons | PASS for selected CPU-reference checks; target math parity unverified |
| AC-006/AC-009 replay and delivery | [Real host rehearsal](evidence/monday-rehearsal/results.json), 11 checks, 12 real GET requests, no errors or execution POST | PASS |
| AC-007 source project | Published 27-file CANN/CPU project; actual factory CPU build/tests and independent detached source rebuild | PASS for source and CPU-reference delivery; native compilation NOT_RUN |
| AC-005 full target inference | Complete target runtime/model implementation, SDK/device/model and original comparison | NOT_COMPLETE; target compile/device/model/comparison NOT_RUN |
| AC-008 model-based Value Agent | Existing deterministic evidence report; configured real provider absent | Real model invocation NOT_RUN |

Corrected-hierarchy backend checkpoint: **133 passed** in 329.666s, [raw log](evidence/monday-rehearsal/backend-tests.log). Subsequent reader-only origin hardening: 10 library tests passed; immutable C5 recording still verifies. Frontend: 26 scoped checks plus 16 projection regressions, production build passed. Real browser checks prove exact full-ref selection, backend-bounded SSE, native CPP/diff agreement with ZIP bytes, complete recorded process log, CPU/native outcome separation, real source download and rewind removal. No frontend timer advances production states. Original C3 recordings retain their earlier library and are not claimed as runs of this corrected candidate.

The initial source-only run `528acf3c90ff4d7c95e67d4fcff15c01` is retained in `recordings/archive/ascend-source-before-inner-pool.zip`; it does not establish AC-010. The original full-model/native goal and overall task remain unfinished. This checkpoint does not change their acceptance threshold.

Independent manager-view re-audit: [findings and actual evidence](evidence/monday-rehearsal/independent-audit.md). The four presentation questions—input, selected inner stages, new cross-parent chain, source/build/log/ZIP output—are understandable in the actual host. Diff capture waits for real source bytes; process capture visibly shows PID 25114, exit 0 and literal CPU352 output. No new production execution was needed for rehearsal.

Final portable-reader follow-up: historical POSIX/Windows-drive/UNC paths are validated lexically, without native-host reinterpretation or access to original paths. Exact path-map keys and original metadata remain unchanged. Final affected reader/path/SSE/export suite: **38 tests passed**, [raw output](evidence/monday-rehearsal/final-portable-reader-tests.log); launcher/library checks: **14 passed**. Linux preflight validates all five packaged recordings and 244 sealed host assets. Cross-platform lexical cases are checked; actual Windows OS execution remains NOT_RUN.

Portable prebuilt release: [fresh-unpack checks](evidence/monday-rehearsal/package-verification-summary.json) verified 1,349 file hashes, sealed host startup, five owned recordings, exact C5 source download and original SSE events with zero execution dispatch. Real guided browser video: 98.27 seconds, 2,933,508 bytes; [capture evidence](evidence/monday-rehearsal/monday-real-replay-summary.json) records nine checks, GET-only factory requests, unchanged recording list and no page errors. Presentation pauses are browser recording interactions; production graph changes remain exclusively original backend events.

Windows startup correction: the original launcher used native Path ordering for source fingerprinting, which case-folds names on Windows. Fixed ordering to original-case relative path components, preserving the existing Linux-generated seal exactly. Five launcher checks pass, including simulated Windows path comparison and rejection of changed source/assets. Original shipped source seal 907896c2d0a3c6cbf95f0f3eddcef609459d35f811d25e46d9ca2a1b138cfd00 and all 244 assets remain validated; no reseal or frontend rebuild. Actual Windows host execution awaits the user's startup result.
