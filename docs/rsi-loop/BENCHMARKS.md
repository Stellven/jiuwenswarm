# Model-free capsule benchmarks

Run from the repository root in Linux/WSL with the project Python environment:

```sh
python -m jiuwenswarm.research_rsi.targets.capsule_benchmark_cli list
python -m jiuwenswarm.research_rsi.targets.capsule_benchmark_cli run --all --output /tmp/ai4r-capsule-baselines
```

The command discovers all selected catalog releases, captures current research source and installed dependencies, verifies the closure, evaluates the selected parent, then measures its A/A noise baseline with the existing paired AB/BA batched runner. No model, installed `/opt` runtime, manual grant, admission or activation is involved. Eight selected deterministic releases have representative fixtures: Calculate m1-4, Table Normalize m1-3, Markdown Report m1-2, typed Calculate/Normalize/Markdown m1-1, Packet Report m1-1 and Summary to Packet m1-1. Typed fixtures are checked through their selected type-fidelity checkers; summary fixtures use the declared `summary` input without manufacturing a packet wrapper. Other releases stay visible as `skipped` with a reason; errors are distinct from skips. A failing or incomplete parent produces an error and no benchmark measurement.

The default command uses each fixture specification's frozen protocol and gates. For a shorter pipeline check (same acceptance gates, fewer samples and smaller batches):

```sh
python -m jiuwenswarm.research_rsi.targets.capsule_benchmark_cli run --all --output /tmp/ai4r-capsule-smoke --config-file docs/rsi-loop/benchmark-smoke-config.json
```

`--config` accepts inline JSON instead. Select targets using repeated `--capsule utility.calculate --capsule utility.table_normalize` instead of `--all`. Reuse an existing capture with both `--runtime-root PATH` and `--runtime-manifest PATH`; its source and ABI pins must still verify. Output directories must be new, preserving previous evidence.

`report.json` contains `tested`/`skipped`/`error` counts and per-capsule results; each measured capsule has its own result, captures and immutable job evidence. Reports retain selected release bindings, source/protocol hashes, effective sizing, raw paired samples, confidence intervals and correctness details. Every result is `local_unprotected`, `UNQUALIFIED`, model-free evidence. A/A compares identical bodies, so `objective_met` and `improvement_claimed` stay false even if clock noise happens to satisfy numeric gates. These baselines establish current-host noise; they do not establish a candidate gain. The shorter smoke protocol is marked as differing from frozen defaults. Preserved historical Codex records remain associated with their historical bodies and protocols.

Generalist m1-2 remains unsupported for this model-free command: the selected worker calls `ctx.model` and requires frozen work-contract/provenance context. A fake model would measure a substituted workload. Builder likewise requires a real governed native agent invocation and its independent task adapter. Both remain visible with explicit blockers; neither is counted as tested. The generic fixture adapter derives a single input port from the selected declaration, so future deterministic non-packet adapters can register data without capsule-name branches.
