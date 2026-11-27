# `ifbench` — Inference Engine Benchmark & Profiling Suite (M2 Lab Integration)

`ifbench` (`v0.4.1`) is the reference benchmark, telemetry, and Nsight Systems profiling toolkit for DGX Spark inference engine evaluation. It uses Python 3.11+ standard library only and integrates with `jiuwenswarm`'s M2 Lab Manager / Lab Agent protocol (`factory.contract/2`, `factory.lab-task/1`, `factory.lab-report/1`).

## Contents

- `benchmarks/ifbench/` — Core `ifbench` package (`run.py`, `engine.py`, `benchmarks.py`, `telemetry.py`, `profile.py`, `proxy.py`, `requests.py`, `bundle.py`, `coverage.py`, `stats.py`, `routing.py`, `gguf_info.py`, `gpu_calibration.py`).
- `benchmarks/ifbench/data/` — Pinned prompt filler, token-probability prompts, and CUDA kernel operator-category map.
- `benchmarks/ifbench/lab_adapter.py` — Thin `CommandAdapter` bridge for `jiuwenswarm.factory.lab_agent`.
- `benchmarks/ifbench/examples/muse-nvfp4-baseline-lab-report-1.json` — Verified `factory.lab-report/1` sample generated from the 2026-11-26 Muse-Spark-Open-816B-A42B-NVFP4 single-Spark baseline run.
- `jiuwenswarm/factory/contracts/muse-nvfp4-spark-v2.json` — `factory.contract/2` contract for Muse NVFP4 on `spark-gb10`.

## Running with M2 `lab-agent`

Start the M2 Lab Agent with `CommandAdapter` pointing at `benchmarks.ifbench.lab_adapter`:

```bash
# Live execution mode (runs ifbench on the Spark host)
export IFBENCH_CONFIG=/path/to/spark-config.toml
export IFBENCH_SET=smoke
jiuwenswarm-factory lab-agent serve \
  --profile spark-gb10 \
  --adapter command \
  --command "python -m benchmarks.ifbench.lab_adapter {package} {output} {payloads}"

# Offline conversion mode (ingests an already-verified ifbench bundle)
export IFBENCH_BUNDLE=/path/to/lab-agent-nvfp4-baseline
export IFBENCH_REV4_DIR=/path/to/rev4-offline
jiuwenswarm-factory lab-agent serve \
  --profile spark-gb10 \
  --adapter command \
  --command "python -m benchmarks.ifbench.lab_adapter {package} {output} {payloads}"
```

## Muse NVFP4 Single-Spark Baseline Summary (2026-11-26, Compact Sample)

- **Model**: `unsloth/Muse-Spark-Open-816B-A42B-NVFP4` (`fc6908f53c6882d4ec48fca5ba144e41d21e1f92`, lossless GGUF V3 container, 528.94 GB)
- **Engine**: `llama.cpp` `ba3c05f` + 3-arg Muse expert global-scale fix (`d166c044`)
- **Performance (3 × 512/32)**:
  - `engine_decode_tok_s`: **0.2289 tokens/s**
  - `e2e_output_tok_s`: **0.0642 tokens/s**
- **Quality & Stability**: GSM8K **3/3 (1.0)**, RULER **2/2 (1.0)**, infer-check determinism **1.0**, truncation **0/7 (0%)**, L2 disconnect recovery **pass**.
- **Bottleneck (separate Nsight Systems pass)**: GPU busy **1.56%–3.49%** (96.5%–98.4% idle waiting on SSD reads / CPU); physical SSD reads **~564–583 GB** per 512-token prefill and **~162–186 GB** per 32-token decode.
- **Telemetry coverage (rev4)**: 60 items (43 `ok`, 10 `unavailable`, 7 `not_applicable`). Required T3 counters for factory-generated engines: `M.expert_tier_share`, `L4.expert_selection`, `L3.step_phase_split`, `L5.fastpath_fallback_rate`.

## Validation

```bash
python -m pytest tests/unit/test_ifbench_lab_integration.py -v
```
