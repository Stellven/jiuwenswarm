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


## Live RSI delivery evidence — 2026-10-29

The [compact evidence index](../../benchmarks/ccbench/rsi/evidence/2026-10-29/index.json) records selected implementations, measurements and SHA-256 provenance. These are benchmark artifacts, not automatically admitted or activated product releases. Earlier model-free results above remain historical and separate.

| Target | Campaign outcome | Selected iteration | Controlled runtime reduction | Live agent comparison |
|---|---|---:|---:|---|
| Calculate | Completed, five iterations / ten model calls | 3 | 23.1% | Four tasks completed |
| Table Normalize | Four evaluated children; fifth diagnosis failed, nine model calls | 4 retained | 16.6% | Not run |
| parse_duration | Four rounds / eight calls; stopped after three without progress | 1 | 17.5% | Not run |

Calculate and Normalize each passed 19 cases across three trials for their selected child. parse_duration passed the original four gate and ten hidden checks across three trials; its timing covers only the three original valid gate inputs, using protected batched execution including amortized startup. Its four proposals produced one distinct implementation. Normalize retains an evaluated child despite an error stop and an unresolved formal containment lease; the additional partner checks and live comparison were not run. No end-to-end production qualification is claimed.

The Calculate live comparison reports mean session wall times of 72.3675 seconds plain, 63.41 seconds CC, and 60.5675 seconds RSI across four tasks, with all answers correct. Three tasks used the selected Calculate worker and the correct-reference control kept its original implementation. Plain/CC rows were reused unchanged from the partner's historical results. The new arm used 19 model calls; runtime/adapter differences and non-contemporaneous baselines prevent an RSI-only causal latency claim. The controlled 23.1% measurement is a separate parent/child comparison.

### Runners and reproduction inputs

`benchmarks/ccbench/rsi/run_t1_rsi.py` provides prepare, validate, preflight, run and score operations for the live comparison; `export_selected.py`, `served_tool.py`, and the runtime build scripts bind the retained selection to the served tool. Use each command's `--help` for its required arguments. `function_rsi.py` provides baseline and run operations using an explicit manifest and source root for pure-function benchmarks; `function_executor.py` and `function_model.py` implement its protected evaluation and real model adapter. The retained function manifest/contract and live run command are included in the compact evidence directory as historical execution inputs.

Reproduction requires fresh run IDs, fresh output roots, regenerated source/runtime pins and the qualified Linux host services; historical absolute paths and consumed grants must not be replayed. Reuse calibration only while its bindings remain valid. Full frozen campaign configurations, model receipts, raw paired measurements, source snapshots and failed attempts are retained in the external consolidated archive, whose filename, size and SHA-256 are in the index. The archive is not committed to Git and does not yet have a shared download URL.

### Delivery checks (2026-10-29)

The focused Linux unit run produced 100 passed and one failed legacy byte-digest assertion in `test_legacy_single_attempt_publications_are_byte_identical`. The same assertion also fails when using the pre-change HEAD publication implementation against the unchanged fixture inputs; that pre-integration run recorded a historical snapshot mismatch. During main integration, the compatibility test was bound to its original carrier path while current-release tests kept dynamic discovery. All six expected hashes remain unchanged, and all 35 publication tests now pass. The full application suite and new model/benchmark runs were not executed for this push.

The focused command used the existing WSL analysis virtual environment: `python -B -m pytest -o addopts= -q --noconftest -p no:cacheprovider tests/unit_tests/research/test_budget_ceiling.py tests/unit_tests/research/test_host_original_trace_sink.py tests/unit_tests/research_rsi/test_capsule_executor.py tests/unit_tests/research_rsi/test_cgroup_lifecycle.py tests/unit_tests/scripts/test_rsi_capsule_publication.py tests/unit_tests/scripts/test_rsi_host_codex_upgrade.py`. `--noconftest` excludes unrelated application-wide memory hooks requiring unavailable `ruamel.yaml`; overriding addopts avoids unavailable global coverage plugins. These tests use their own local fixtures.


### Main integration checks (2026-10-29)

The merge preserves the current main release account-fingerprint fence, prompt hashes and automatic-routing call allowance alongside RSI declaration-driven Builder modes and deferred work clocks. The protected-stop path now handles an unstarted work clock without a KeyError while still enforcing model-call exhaustion. The existing scheduler budget cases cover this correction.

Focused component verification on the merged source: 93 unique Builder/prompt/budget/routing/scheduler checks passed; all 35 publication checks passed; 32 Codex subscription tests plus six subtests passed; two capsule asset tests passed. Read-only release validation verified scientific/PI pins, compiler assets and static-template bindings against final source bytes. Three held-start scheduler tests and one Codex launcher test are environment-blocked in the lightweight analysis environment (missing pinned openjiuwen/application dependencies). They are not counted as passes. No full application acceptance, new model calls or benchmark replay was performed. Previously saved benchmark results remain tied to the executed source snapshots in their archive, not a new performance claim for the merge commit.
