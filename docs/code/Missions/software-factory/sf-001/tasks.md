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
