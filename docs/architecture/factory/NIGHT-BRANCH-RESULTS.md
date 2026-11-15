# Night round results: Strata and factory methodologies

These are exploratory measured results. The engine is the locally source-qualified fixed-placement Strata build 89ae0ee6123597636ef162dec826230186c00f3b, not an unmodified upstream image. Model pack, full-six routing, precision, CPU8 and runtime limits remain fixed.

## Actual model: pg512/tg128

Order A–B–C–C–B–A, two fresh cells per profile. Each cell runs eight ARC questions in one process and four speed requests in another; discard the first speed request. Twelve containers completed and were removed. No JiuwenSwarm agent, build or CPU benchmark ran alongside GPU measurements.

| Profile | Combined generated tokens/s | Decode tokens/s | Prefill input tokens/s | Sampled ARC answers |
|---|---:|---:|---:|---:|
| A: 76 GB expert budget, chunk256 control | 8.527 | 13.889 | 88.33 | 16/16 |
| B: 68 GB budget, chunk256 | 9.245 | 13.781 | 112.34 | 16/16 |
| C: 76 GB budget, chunk1024 | 10.605 | 13.983 | 175.62 | 16/16 |

C has a pooled **24.38% combined-rate gain** and **0.67% decode-rate difference**. Its two cells are 10.596 and 10.615 combined tokens/s. Control A varies from 7.800 to 9.402: the symmetric first/last comparisons are approximately +35.8% and +12.9%, so the magnitude is not well established. The improvement is primarily prefill.

B has a pooled +8.42% combined rate, but the reverse comparison is slightly slower than control. Do not call this a repeatable speed gain. Its declared resident budget is 8 billion bytes smaller, resident expert slots fall from 8843 to7911, and the speed processes show about8GB more minimum host-available memory. That is useful headroom evidence, not a total GPU-memory measurement.

All eight quality answers and their generated tokens match across profiles, 8/8 in each repeat. Every long speed output differs across profiles while remaining exactly stable within each profile. Consequently the runs do not pass an exact-output-equivalence gate. Eight questions cannot establish noninferiority; no configuration is promoted.

### Memory accounting

| Cell | Profile | Minimum host available (GiB) | Cgroup kernel peak (GiB) |
|---|---|---:|---:|
| 1 | A | 32.94 | 10.37 |
| 2 | B | 40.92 | 28.63 |
| 3 | C | 34.16 | 20.52 |
| 4 | C | 34.17 | 19.83 |
| 5 | B | 40.93 | 27.08 |
| 6 | A | 33.45 | 18.77 |

Reported cgroup peaks are the maximum kernel-peak counter observed by the sampler; a disappearing cgroup can prevent a final read. They include their own accounting/page-cache effects and do not account for all GPU driver allocations on Spark. They cannot be added to host estimates or used as exact GPU peaks. Cgroup usage rises in some lower-residency cases; this is retained rather than hidden. All memory guards and OOM checks passed.

## Component and factory rounds

- Native lifetime arena:30→14MiB allocation,53.33% reduction; live bytes verified. Synthetic scratch example, not measured engine savings.

- GPU expert dispatch batching:3.01–21.75× versus serial FP32 route launches across four small shapes. All variants pass the CPU oracle. Fixed-order sweep and best-tile selection are optimistic; this is not Strata model throughput or an existing optimized-kernel comparison.

- Cohesive factory analysis batch:1.241→0.170s,7.28× for the seven-operation job. Fresh inventory parsing:90.413→32.209ms,2.81×. Isolated actual Host:170.422→111.822ms,1.52×, with identical outputs/provenance and preserved grant denial. Production Host unchanged; optional source-pinned CC patch is available.

## Evidence and failure retention

Raw model evidence: `ROOT/night-branch-engine-v2/`; offline counters: `ROOT/night-branch-analysis-v1/`; native component source and ROUND1 records are in the CC packages, binaries in `ROOT/runtime-native-artifacts-20261115/`. Factory raw repeats and receipts are in `cc-workflow-efficiency-002/` and `cc-native-inventory-once-002/`.

Engine v1 stopped before GPU submission because a nested source-pin path was rejected; v2 pins that component separately. Metadata benchmark001 had a harness assertion that expected failed instead of the correct blocked grant-denial state;002 corrects the assertion and retains both attempts. An initial full test command lacked the required external lab-source setting and exposed two stale test assumptions; its failure log is retained. No missing dependency was globally installed.

Long-prefill results, verification, live branch mission and handoff identities follow below.

## Actual long-prefill confirmation: pg4096/tg16

Four fresh processes in A–C–C–A order, three requests per process with the first discarded. Same image and76GB fixed expert budget; chunk256 versus1024 is the only profile change. Mean native prefill+decode latency falls **28.221→17.717seconds**, a **37.22% reduction**. Combined generated-token rate is0.567→0.903tokens/s (**1.593×**); prefill input rate is150.92→246.22tokens/s (**1.631×**). Decode remains14.80tokens/s in both arms. Low combined output rate here reflects4096input tokens for only16output tokens, not slow decode.

The repeated long-prompt request produces exactly matching token IDs and finish reasons across all four processes, including warmups. Each speed workload uses one distinct prompt repeated within processes; neither is a diverse prompt corpus. All startup placement aggregates match. Both paired comparisons improve; magnitude remains a small-sample descriptive estimate. Startup/tokenization/client latency is excluded. Raw logs and frozen source closure: `ROOT/night-long-prefill-v1/`.

## Methodology improvement discovered during the round

The initial zero-shot ARC prompts all fit one256-token chunk, so their matching answers did not adequately exercise the chunk treatment. The prefill CC now provides a bounded coverage tool that predicts chunk counts before an agent spends a lab run. It flags this blind spot without claiming actual runtime engagement. A new16-question ARC-Challenge subset uses eight disjoint training demonstrations per prompt; its560–619-token inputs predict three baseline chunks versus one candidate chunk. Dataset revision, train/test IDs, tokenizer and construction are frozen; this is an adapted few-shot generation check, not an official ARC score.

Factory batching and metadata speedups overlap in the costs they remove; they must not be multiplied into a projected combined gain.

## Longer-prompt correctness result

All four adapted eight-shot ARC16 processes completed: **16/16 correct for each arm in each repeat**, all answers valid, no per-question regression, and every generated token/finish exactly equal across arms and repeats. Inputs span560–619tokens; actual startup chunks256/1024 were verified and all16cases have different predicted chunk counts. This closes the particular short-prompt coverage gap. It remains16unique questions, not64independent questions or population-level quality certification. The differing pg512/tg128 long generations from the first round remain an unresolved exact-equivalence failure; they are not erased by these successful tests.

Across the three manual campaigns, **20 phase containers** completed and were removed. Raw input wire, output, native stderr, one-second samples, Docker boundary evidence and manifests are retained. Separate historical source snapshots preserve the exact code used in each frozen run, including the initial budget parser before its later malformed-log guard was tightened.

## Final verification and portable runtime

Before the final evidence-intake addition, the full factory suite passed **1097 tests,1 skipped**, using the project-local test environment and an explicitly configured external lab-source path. The earlier failure log is retained: the first invocation missed that path, and it exposed stale PYTHONPATH/pure-wrapper test assumptions which were corrected. The final launcher-specific six tests also pass, including deadline refusal, bounded evidence intake and crash-safe partial-receipt export.

The earlier38-package standalone ARM64 agent image was `sha256:1f89c15d623fd14b6c9601da2a65adb3f37bc337ac4ed316b8e943671e03ff98`. It successfully imports the actual JiuwenSwarm facade and seals38top-level CCs (46including nested components). No global dependencies were installed. Native experimental binaries remain explicitly tagged ARM64 artifacts outside portable source CCs.

A final real Host invocation of the built GPU-kernel CC with `process.exec`/`gpu.use` and a boundGPU0 handle passed its numerical oracle. This was a functional transport/grant smoke during CPU analysis activity; its timings are excluded from performance claims. The optional metadata optimization remains a source-pinned component; the production Host source was not modified.

## Live JiuwenSwarm branch investigation

The actual JiuWenSwarm facade with gpt-6.1-sol completed a CPU-only evidence investigation in1029.05seconds. It created five branches, forked three times, refined one branch, pruned one and attached observations before comparing. Thirteen successful analysis calls covered scratch liveness, native budget/host memory, prefill coverage, factory overhead and methodology transfer. All mission obligations passed; no active jobs or incomplete receipts remained. GPU engine runs above were performed manually; this mission demonstrates evidence-driven investigation and next-input generation, not unattended weeks-long engine optimization.

The agent retained unknown Pareto measurements and reported inconclusive rather than promoting a candidate. Its next proposed contract investigates the first differing generated token under a shared teacher-forced history; root independently checked first divergence at zero-based output index49 (baseline10367, candidate32187). The required logit/reference tool is a recorded gap. Full agent report and proposal are in `night-branch-jiuwen-v1/AGENT-REPORT.md` and `NEXT-INPUT-PROPOSAL.json`, exported by root from the agent's immutable observation after its local report-file writes failed. The original observations, repaired tool errors and trace are retained.

Factory cost was visible:37 evidence reads and13 useful analysis calls. Provider cumulative usage reports5,582,181 input tokens, including5,432,960 cached input, plus36,860 output; these are repeated provider accounting totals, not unique context. Branch/evidence skills now advise reusing returned state, bounded artifact intake and immutable report observations. These skill changes have not yet been measured in a second live mission.

## Evidence intake CC added from observed factory costs

`factory.evidence_digest_lab` provides task-local JSON indexing and exact pointer projection, a systematic intake skill, examples and verification units. Source hashes and pointer provenance accompany values; omissions are explicit; malformed/nonfinite/duplicate-key JSON, cross-task access and byte/cardinality/depth limits fail rather than truncate. It performs no scientific summarization.

One actual Host round on copied engine, quality and factory reports read124,876 raw bytes (53,127 canonical parsed bytes) and returned a10,326-byte native success envelope. Selected values and source hashes matched exactly. This measures response bytes, not agent token/time savings; no second live mission was run. Evidence: `ROOT/night-evidence-digest-qualification-003/` (earlier successful development snapshots001/002 retained). The new library now contains39top-level packages,47including nested components. Seven new job packages were added during this round; existing prefill, profiler, evidence and branch methodologies were revised.

The final digest-suite attempt found three stale telemetry assertions expecting evidence CC version1.0.0 after its materials/schema revision to1.1.0; actual telemetry was correct. Updated assertions and retained the failed log. No application behavior was changed to satisfy those assertions.

Final release verification: **1114 passed,1 skipped**,130.38seconds. Final standalone ARM64 image `sha256:4e25f0ec7200b28f348aa0a3ce753ea1c5b5306e70ea8cee525ae03d862fafa3` imports the actual facade and seals all39top-level packages. It includes the evidence-intake CC and revised skills. The earlier38-package export is preserved separately.
