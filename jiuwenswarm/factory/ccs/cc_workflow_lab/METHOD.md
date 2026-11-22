# CPU factory workflow lab

The useful unit of work is a cohesive analysis job. This package analyzes inline
receipt summaries, estimates costs from explicit measurements, and measures only
one bundled finite CPU fixture. It cannot execute commands, accept source paths,
call another CC, grant effects, or recursively batch. Native `process.exec` is the
host's grant to launch this trusted-local package, not sandbox isolation.

Historical fixture: 24 native invocations across seven research qualification
packages. Source SHA256 values identify the original JSON records; rows retain
call/release identity, elapsed seconds, state and completeness. Projection strips
large package inventories. These observations do not isolate worker startup,
sealing, analysis or GPU time. No GPU/model-quality/admission claim follows.

`benchmark_fixture` executes at most 32 repetitions over this exact fixture. It
reports raw perf-counter durations, median, Python traced allocation peak, and
Linux lifetime process peak RSS (KiB). RSS includes the interpreter. Tracemalloc
adds overhead; compare the same instrumentation. First repetition is exposed,
not silently discarded. This is a small CPU analysis benchmark, not an inference
kernel benchmark.

The separate host benchmark records cold seal separately, warm source hashing,
sealing, native subprocess end-to-end, direct analysis and actual Host calls.
Host timings include authority checks, dependency provenance and receipt I/O.
A replayed invocation key is tested separately and never counted as fresh work.
ABBA comparisons keep the exact JSON inputs and outputs matched. Release reuse
requires an already sealed appropriate implementation; it is not source-change
caching. No host/protocol modification is required.
