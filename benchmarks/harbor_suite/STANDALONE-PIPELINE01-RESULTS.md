# Standalone Pipeline01 results — 2026-10-26

This is agent-authored research and delivery evidence from the public workload
rehearsal on branch `benchmark/pipeline01-standalone`, based on
`b983328d62fd8c5bfe7825bc6dd259f31e39ba85`. Native AI4R E1 is **NOT_RUN**;
the governed full task remains **UNSCORED**. These notes are not native stage output.

## Sources, screening and hypothesis

Only the eight staged public files, assignment and public manifest were read as
task inputs. Public source-notes.md supplies the technical rationale: a full
rebuild inserts every remaining posting, while replacement removes old postings
and inserts new postings. Screened it as directly relevant executable development
evidence, with public/reference_index.py as the supplied POC implementation.
Public/protocol.json freezes tokenization, hypothesis, measurement boundaries,
seed, repeat order and scientific decision criterion; public/workflow.json
describes the desired governed lifecycle but supplies no native execution authority.
The handoff schema permits ns and ms individually; their agreement needs an
additional semantic check. No downloads, external literature or inference calls
were needed. No case archive, referee, private grading materials or prior expected
answers were inspected.

Frozen hypothesis: “Incremental updates reduce total logical posting mutations
relative to full rebuild while preserving exact postings and conjunctive retrieval.”

The unchanged reference source was used as the POC. The added runner supplies
reproducible dispatch, pre-dispatch validation, evidence retention and public-data
correctness checks. It does not reimplement the treatment or simulate observations.

## Initial measurements (run-01)

Raw output: `D:\Codex Development Runs\pipeline01-standalone-20261026\results\standalone-run-01`.
All 12 launched reference processes exited 0. Every repeat matched independently
reconstructed exact cumulative postings digests and all seven query answers after
each of two batches. Both roles used identical public workload snapshots. Seed
4101 fixed Python hash ordering; repeats were indexed 0, 1 and 2.

| Variant | Baseline mutations per batch | Treatment mutations per batch | Scientific result |
| --- | --- | --- | --- |
| sparse-positive | 318, 316 (total 634) | 18, 14 (total 32) | PASS |
| dense-negative | 384, 256 (total 640) | 704, 640 (total 1344) | FAIL retained |
| conflicting-units | no experiment | no experiment | NOT_RUN; halted |

Operation counts were identical in all three repeats. Treatment reduced sparse
logical work by 602 postings (94.95%) but increased dense work by 704 (110%).
The dense negative finding is a scientific result, not a process execution failure.

| Variant/role | Raw batch update timings per repeat, ns | Median per batch, ns | Median total, ns |
| --- | --- | --- | --- |
| sparse baseline | [380900,342800]; [187500,175200]; [170200,175500] | 187500,175500 | 362700 |
| sparse treatment | [15300,10300]; [18700,12400]; [17300,11500] | 17300,11500 | 28800 |
| dense baseline | [177400,108700]; [189300,112500]; [212600,130600] | 189300,112500 | 301800 |
| dense treatment | [385600,340600]; [327700,284400]; [360500,314600] | 360500,314600 | 675100 |

These small CPU observations show lower sparse treatment latency and higher dense
treatment latency in this run. They do not establish a guaranteed speed advantage
or generalize to other workloads or hardware. Actual perf_counter_ns differences
were emitted by the frozen reference; operations were never relabeled as time.
Timing medians of totals are computed from paired-batch totals, independently of
the medians per batch.

## Final runner verification (run-02)

The final runner additionally aborts invalid correctness/integrity observations
as NOT_EVALUATED, reads process time/memory limits from the protocol, and labels
its required/enum handoff check precisely. Its actual invocation is documented in
the reproduction README. Run-01 was preserved without modification; this final
source was rerun under a new output namespace, `results/standalone-run-02`.

All 12 processes again exited 0 and passed all public-data correctness checks;
mutation counts and scientific findings were identical. Conflicting-units again
launched zero processes. Final-run actual update timings are retained below:

| Variant/role | Raw batch update timings per repeat, ns | Median per batch, ns | Median total, ns |
| --- | --- | --- | --- |
| sparse baseline | [161100,172800]; [179300,166800]; [187700,145300] | 179300,166800 | 333900 |
| sparse treatment | [16100,10500]; [18400,12100]; [16000,10500] | 16100,10500 | 26600 |
| dense baseline | [204700,121300]; [210700,145000]; [207400,124000] | 207400,124000 | 331400 |
| dense treatment | [396100,329900]; [324400,298100]; [1118500,992400] | 396100,329900 | 726000 |

The dense treatment's third repeat is slower; it is retained without filtering.
Each inventory was independently rehashed (57 listed files; 107856 bytes in
run-01 and 109388 bytes in run-02, excluding the inventory files themselves).
The final runner matches the run-02 source snapshot byte for byte.

## Integrity, halt and limitations

The ns/ms conflict in public/conflicting-units.json#/handoff was schema-valid but
semantically incompatible. The runner rejected it before subprocess launch;
`launched_processes` is 0 and no experiment command or stdout exists for that
variant. The original reference already contains a CLI guard; this run's guard
operated before calling that CLI.

All eight original public input hashes and snapshot hashes still match the staged
manifest. Exact command argv, stdout/stderr, environment, source snapshots and
timestamps are retained with a SHA-256 inventory. No case/oracle definitions were
changed. No Docker containers, WSL, relays, RSI/MR files or port 5175 were touched.

Experiment execution per variant took under one second by runner wall clock,
well below 900 seconds; each child completed below its 10-second limit. Concurrency
was one reference child at a time. Observed Windows memory counters were below
256 MiB but cover the launched process only, potentially a venv launcher rather
than its descendant workload process. Thus actual workload/aggregate physical and
committed memory compliance is not established. Aggregate agent memory is not
observed, and memory/disk/network/GPU restrictions are not OS-enforced by this run.
See reproduction README and environment.json for enforcement details.

Delivery consists of these notes, reusable runner and preserved raw evidence.
No native stage, gate, contract, executor qualification or governed acceptance was
fabricated. Later actual AI4R execution and grading remain required.
