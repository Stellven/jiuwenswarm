# Diagnose before selecting components

Use this when the objective is broad, such as “make the decoder faster.” Read the contract and query evidence first. Call `diagnose` with existing JSON report artifact or observation IDs in the current task. Import authorized prior evidence through the evidence CC before analyzing it here; do not invent successful runs.

The tool exposes descriptive rates, repeatability, failures, a vocabulary of alternative causes, and report-backed inspection candidates. It does not identify a causal bottleneck from throughput alone. Its recommended inspection is a prerequisite to investigate, not an instruction to launch, an optimization score, or an agent decision. Publish your own evidence-citing decision before acting.

Inspect telemetry completeness/recovery first, then correctness and repeatability. Consider decode/prefill, placement, physical IO and readiness, CPU scheduling, caches and drafts. A missing measurement is unknown, never zero. Strata already contains expert streaming; inspect it rather than assuming another filler is needed.

Preserve the original input and failed/null attempts. Requested switches do not establish effective mechanism engagement. Source and image identity, full-model obligations, cache state, and observer overhead belong in the analysis. Descriptive min/median/max across different requests are not a treatment effect or confidence interval.

Use the other methodology capsules to prepare cache controls, one-hypothesis ablations and a follow-up proposal. Native analysis is read-only. Neither producer prose nor generated ontology can change operator authority or a scored contract.
