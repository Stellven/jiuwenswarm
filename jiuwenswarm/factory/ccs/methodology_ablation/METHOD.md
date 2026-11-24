# One hypothesis at a time

Do not apply all available CC components because they exist. Identify a report-supported uncertainty, inspect its applicability, and choose one changed variable. Call `ablation` with evidence IDs and, optionally, the selected candidate ID to obtain a bounded design. Unknown candidates are rejected.

First establish independent A/A validity with the frozen correctness/cache protocol. Within-cell matching output is useful evidence but does not freeze a baseline. Missing correctness, engagement, resource or observer evidence blocks scoring. Diagnostic A/A and traced runs may resolve uncertainty without claiming a gain.

For a scored treatment use fresh-container ABBA blocks, identical workloads and controls, at most three trials per hypothesis, and the existing acceptance gate. Record failed/null trials and stop on quality, memory, evidence or budget violations. Never change a reference after seeing the candidate.

Observability components require useful signals and bounded overhead, not a speedup. Source dependencies may remain dormant for dependent experiments; runtime enabling requires separate evidence. After individual ablations, compare the combined stack directly against the original. Do not multiply individual gains.

This capsule proposes designs only. It does not execute, score, keep components, freeze contracts or widen grants.
