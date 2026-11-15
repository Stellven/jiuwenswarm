# Broad Strata configuration campaign: source-grounded leads

Prepared 2026-11-14 for the operator-authorized initial ten-experiment campaign.
Hard stop: midnight America/Toronto at the end of November14, which is
2026-11-15 05:00 UTC. This document proposes experiments; it records no new GPU
measurements, accepted speedups, runtime changes, or promotions.

Source inspected read-only: `/home/user2/strata-baseline/Strata`, revision
`ffa80d73133ea5c548aefe57889a16e8085a938f`. References below are to
`src/dsv41/ds4_model.cu` at that revision unless stated otherwise. No papers are
needed to justify these already-implemented mechanisms. Historical evidence is
in `SPARK-BENCHMARK-RESULTS.md`, `SPARK-FACTORY-EXPERIMENTS-2026-11-14.md`, and
`SPARK-AGENT-IMPROVEMENT-2026-11-14.md`; their contracts stay unchanged.

## What the evidence already establishes

Chunk256 versus512 passed the earlier sampled ARC/combined-throughput contract,
but the subsequent narrow prefill screen produced different first output tokens
(9544 versus5), with within-process repeatability. That screen correctly stopped
without confirmation. This does not establish which token is right or the cause.
Do not treat chunk512 as a correctness-qualified baseline. Native drafting
improved warm decode in its prior experiment but slowed the complete512/128
request. Neither result establishes a general default.

The baseline's warmup is a material confounder: historical prefill advantage
decreased across request positions. Fresh processes do not make the OS file cache
cold. A/A repeatability and position-level retention precede interpreting a new
configuration effect. Do not drop host caches or change host services to create a
different baseline during this campaign.

## Ranked settings and a ten-experiment budget

Use the current admitted baseline: chunk256, dspark none/request spec0, all six
target experts, mmap on, static expert placement, existing model/image/data pins,
unchanged reserve, host guard and cgroup limits. The deployment conservative JSON
is a source of knob values, not automatically the exact frozen benchmark profile.
Apply each treatment to the actual pinned input profile. Each comparison below is
one whole experiment, not one process or CC call. Rank is scientific priority;
the agent can skip an unengaged or inadmissible treatment and record why.

| Slot | Comparison against baseline | Hypothesis and engagement evidence | Correctness/resource concern |
| --- | --- | --- | --- |
| 1 | A/A, distinct fresh processes | Same profile produces repeatable output and bounded timing drift; retain every request position and both raw streams | A/A mismatch invalidates exact-output screening; diagnose before judging candidate equality |
| 2 | `DS4_ENGRAM_THREADS=2` to4 | Parallel row reads hide more I/O; source3400–3420 and3486 startup must report4; require Engram rows/reads on the exercised path | More threads share CPU and DRAM with expert workers; source3411 documents unexplained Metal nondeterminism at larger counts, not a demonstrated CUDA bug |
| 3 | `DS4_ENGRAM_CACHE_MB=64` to256 | Larger row cache avoids repeated reads; startup3486 reports capacity; request-delta cache hits/reads at7955–7960 distinguish reuse from a label change | Additional192MiB competes with file pages; repeated identical prompts favor this mechanism and limit generalization |
| 4 | `--cpu-threads 4` to2 | Fewer workers can reduce contention/spinning and leave launch/reader time; source6843 sets pool bound; retain reported actual lane count | CPU pool includes the helping service thread; explicit count disables native autotuning6876; arithmetic/reduction differences require quality checks |
| 5 | `--cpu-threads 4` to6 | More expert workers can reduce CPU critical path; same engagement checks as slot4 | Keep total container CPU quota unchanged; additional Engram/service/main threads can oversubscribe that quota |
| 6 | `DS4_ENGRAM_THREADS=2` to1 | Serial row reading can reduce thread/lock overhead for warm page-cache hits; actual startup count required | An expected speed loss is useful falsification; preserve actual failure or null evidence |
| 7 | `DS4_ENGRAM_CACHE_MB=64` to0 | Cache bookkeeping might cost more than saved reads for this workload; startup must show0 rows, with nonzero row demand | This is a mechanism ablation, not a likely optimization; verify zero-capacity handling through meaningful package qualification before launch |
| 8 | `DS4_AHEAD=0` to1 | Native next-layer router predictions overlap file reads with current-layer work;1326,3762,9530,14131 implement the real DeepSeek CUDA path | Extra router work, wrong guesses and page-cache churn can dominate; retain predicted/requested/hit counters and all six authoritative picks |
| 9 | `--vram-experts 0.5` to0.6, if admitted | More statically resident experts may reduce CPU expert demand;3570 computes room and load-time placement records show whether resident bytes/count change | Shared DRAM is counted once; unchanged reserve/headroom/guard. Reject on resource pressure or unchanged placement; do not weaken guards to obtain engagement |
| 10 | Independent confirmation of the best surviving setting, or A/A diagnostic if none survives | New paired process order checks whether the screen persists; directly test final chosen configuration | A screen is provisional. No successful confirmation means no accepted improvement. Do not fill the slot with an unsafe or no-op treatment merely to reach ten |

Slots2–9 are single-factor screens. A combined stack is a new intervention requiring
its own direct test; gains cannot be multiplied. Slot9 is lower priority than
confirming a strong earlier signal. If the actual frozen baseline differs from
these numeric values, regenerate a reviewable comparison rather than mislabeling
the treatment. The final executed manifest and receipts supersede this proposal.

## Settings to defer or avoid misinterpreting

`DS4_ASYNC_T=4` is the maximum asynchronous **window row count**, not the number
of worker threads (1323,10859,13234). Raising it to8 with one-token decode and
chunked prefill may do nothing. It is not an independent cheap thread experiment.
Prove rows4–8 traverse the changed branch before spending a slot. With drafting
off this is especially unlikely to discriminate a treatment.

`DS4_AHEAD_EXTRA=-2` limits next-layer guesses to four when the target takes six
(14134), preserving target routing. It is a plausible follow-up to an engaged
lookahead screen, but requires explicit profile/env admission; do not silently
expand the current whitelist. `DS4_AHEAD=2` adds another predicted layer and more
traffic; defer until one-layer read-ahead survives.

`DS4_HEAD_PER` changes head column batching (13290). With one output row it often
cannot engage. `DS4_CACHE_THREADS` has no effect when adaptive expert caching is
off. `DS4_STORE_THREADS` and store policy cannot engage while the store is off.
Do not change cache implementation, cache size and prefetch together.

Do not force `DS4_COPY_ALL=1` for this oversized pack. Do not enable
`DS4_STORE_ZC=1` as a generic UMA optimization: source6570 explicitly warns of
shared-memory budget/fault risk and timing-dependent GPU versus CPU expert
arithmetic. Keep model/expert count, quantization and host reserve fixed.
Chunk1024 is not a second meaningful chunk treatment for a512-token prompt
unless it changes effective execution; it also inherits the open chunk-parity
question. A requested chunk128 ordinarily rounds up to256 (2806).

## Experiment and package methodology

Treat CCs as job packages: methods, supported configuration surface, independent
qualification, submission, lifecycle and retained evidence form one usable
capability. A pile of standalone setters does not establish a new optimization.
The methodology/lab package should choose the cheapest discriminating scope;
the Strata workbench should produce immutable profile pairs and engagement
expectations; package qualification should verify exact changed fields and fixed
invariants; the loop should select/submit/collect with the original raw receipts.
Capability admission and the actual operator deadline remain host-enforced.

The broad objective is native throughput. Use prefill, decode and combined native
time from a frozen common workload, and report them separately. A prefill-only
screen cannot establish complete-request gain. A decode-prefetch treatment needs
multiple decoded tokens: one-token prefill screens cannot establish useful
lookahead benefit. Retain tokens and native boundaries; do not substitute wall
time with model loading for native combined time or vice versa.

Freeze quality criteria before looking at candidates. If the broad campaign uses
a sampled quality/noninferiority gate rather than exact token identity, state the
new contract explicitly and retain cross-arm token changes as observations. It
does not resolve the earlier exact-parity failure. At minimum, A/A repeatability,
valid output extraction, full-six routing, absence of draft tokens and meaningful
quality coverage are required to interpret screens. A semantic regression gate
does not prove bitwise equivalence. Per-position speed measurements must survive
the predeclared warmup protocol and resource/cleanup checks.

Use short AB screens for breadth, then an independent balanced confirmation for
the strongest survivor. Record exploratory selection and small sample size;
screening multiple settings increases selection optimism. Keep all negative,
failed and unengaged results. Do not reuse confirmation observations to choose
its threshold. Estimate each next experiment's worst-case duration and cleanup
margin before launch; stop admission early enough to enforce the midnight hard
stop on active work. Agent turns, builds and source inspection must not overlap
quiet GPU measurement where the frozen campaign requires isolation.

## Available observability and an important boundary

There already is a native expert routing emitter: `DS4_TRACE=file` at9433 writes
layer/window/expert IDs; `DS4_TRACE_AHEAD` appends predictions. Thus missing live
trace work means factory capture, decoding, completeness and read-readiness
qualification, not absence of a native routing emitter. A routing trace alone
does not identify disk-read readiness or prove critical-path stall savings.
Native Engram hit/read/cache counters exist at7955; router prediction hit/rank
counters exist at9479–9527. Prefer existing uninstrumented outputs where they
are retained. File I/O counters, CPU time and memory samples are supporting
evidence, not attribution proof.

Do not re-enable `DS4_PROF` in the throughput screen: its previous exit139 remains
unresolved. A separately authorized observer qualification must establish crash
behavior and overhead before instrumented timing can be interpreted. Runtime
flags printed in a receipt prove configuration, while actual changed placement,
cache demand or prediction demand proves mechanism engagement.
