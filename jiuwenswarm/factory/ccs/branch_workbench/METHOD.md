# Evidence-driven branch exploration

A branch is an ordinary `investigate` node in the existing immutable, revisioned task graph. Parent lineage is independent of execution dependencies: alternative forks can be ready together. `refine`, or `fork` with `continuation: true`, depends on the parent's completion. The real JiuwenSwarm agent chooses each action. There is no scheduler, graph executor, intent compiler, registry or additional execution tool.

All mutations require `expected_graph_rev`, an existing current-task `decision_rev`, and `idem_key`. Retrying identical inputs returns the original revision. Reusing a key with different inputs fails. Ordinary graph changes and branch changes share the same CAS boundary. Source task, hypotheses, parent lineage and resource allocations persist across restart and evidence export. Branch hypotheses and allocation are immutable: fork to refine. The workbench reserves cumulative `cpu_seconds` and `gpu_seconds` across all branches, including pruned branches, under `constraints.branch_workbench`. Defaults are eight branches, 60 CPU seconds and zero GPU seconds. Reservations are accounting limits; actual CC execution still requires existing task allowlists, grants and job admission.

Use `attach` to finish a branch with qualitative evidence and an explicit outcome. Current-task evidence IDs must exist. This is useful for applicability, methodology, missing data or failure receipts. No speed/memory/quality vector is inferred from such evidence.

For `record`, publish an observation whose `values.branch_measurement` contains:

```json
{"comparison_key":"sha256-of-frozen-comparison-description","scope":"offline_replay","metrics":{"throughput_tps":null,"peak_memory_bytes":null,"quality_score":null},"cost":{"cpu_seconds":1.2,"gpu_seconds":0}}
```

Allowed scopes are `configuration`, `offline_replay`, `subsystem` and `end_to_end`. Define one comparison description with hardware, workload, phase, units, decoding, metric definitions, quality rule and correctness sample. Use its stable digest as the comparison key for genuinely comparable results. A reported quality score is only comparable under the same rule. Missing keys or null metrics remain unknown. Use actual measured costs, never made-up timing or projected gains. Raw receipts, artifacts, repeatability and confidence still matter.

`compare` groups identical keys and scope, includes only complete throughput/memory/quality vectors, and returns the nondominated frontier (maximize throughput and quality, minimize memory). Unknown or partial vectors stay in `unknown`; scalar component scores cannot become accepted end-to-end gains. Reported measurements may originate with the agent and are explicitly not host-verified acceptance evidence. Existing contract acceptance gates remain unchanged.

The package cannot launch CCs, choose a branch, alter grants, mutate a contract, free consumed reservations or promote a component. A branch's optional `capabilities` list describes potentially useful tools, each subject to the normal release/capability task policy when actually called.
