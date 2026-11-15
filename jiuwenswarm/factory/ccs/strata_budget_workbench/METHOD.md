# Resident-budget experiment

Hypothesis: fewer resident experts reduce device allocation but increase demand transfers. Use the source-qualified fixed-placement image; freeze its source/build identity. Hold model, routing, quantization, CPU workers, prefill chunks and workload constant. Use apply to vary only DS4_EXPERT_BUDGET_BYTES. The parser requires the runtime to report requested=effective and sufficient safe budget, all 40 layer placements and a matching aggregate hash.

Start with a small change and short quality screen, then paired fresh-process runs in counterbalanced order. Budget and placement differ intentionally across arms; require stability within an arm. Check exact output and ARC answer changes independently: matching answers do not mean identical numerics. Do not promote from eight questions or one timing pair.

Memory sampling records cgroup memory.peak, memory.current, host MemAvailable and optional process VmRSS/VmHWM. Peak includes accounting/page cache and is not exact GPU memory; shared-memory Spark driver allocations can differ from cgroup accounting. Do not add these metrics or label budget reduction as measured peak reduction. Report reserved budget, resident expert count, recorded peak and host minimum separately. Missing counters stay unknown.

Verification units test pure transforms, unsafe/malformed budget rejection, placement corruption and memory accounting. They do not certify the engine or grant GPU execution. Native runtime guard, durable logs, deadline and owned-container cleanup remain mandatory. A crash is an outcome to retain before choosing a new branch.
