# Standard native Strata comparison v1

Operator freezes a new contract; the agent can submit, reconcile and read results.
A contract is an input, never a proposal the worker may relax after measurement.
The verified drafting component produces A/B profiles differing only in dspark.

Correctness uses a deterministic 64-question ARC-Challenge test subset, four fresh
processes per arm, exact answer-letter generation, native greedy decoding and full
six-expert routing. Pilot questions come from the disjoint train split. This is a
sampled generative regression test, not official ARC likelihood/acc_norm scoring.
All answers must be valid; baseline accuracy >=50%; every question's B correct
count must be >= A's count. Existing token-golden contracts remain separate.

Speed uses four repeated real-text 512-token prompts, 128 generated tokens each,
one warmup plus three measured requests, prefix reuse disabled, no EOS. Report
native prefill and decode separately. It borrows workload sizes from llama-bench,
not its execution implementation. Native sampling remains included. Frozen main
order ABBAABBA gives four adjacent process pairs. Require geometric mean B/A >=
1.05 and seeded paired bootstrap 95% lower bound >1.0. This small sample does not
establish performance or quality on other workloads. Measured B must actually
offer and accept drafts. No automatic promotion or default activation occurs.

Exclusive lab lease, host memory admission/guard, bounded deadlines, immutable
image, read-only assets, per-phase source/input pins, durable streams and recovery
retain partial failures. No builds/agent work during GPU measurement. On completion
verify the evidence manifest, exact wire, boundary and native counts independently.
Public data provenance, license and source responses are retained beside dataset.
Host capabilities use the existing bridge when containerized; no Docker socket is
provided to an agent. The operator CLI is deploy/spark/compare-benchmark.py.
