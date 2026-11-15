# Research cache and streaming CCs

Two independent native CCv2 bundles are available under `jiuwenswarm/factory/ccs/`: `expert_cache_lab` and `ssd_streaming_lab`. They import their own bundled stdlib runtime. They require only `python` and `process.exec`; no factory bridge, GPU use, server, install, model weights or arbitrary path input is involved.

| Capsule | Capabilities | Useful result |
|---|---|---|
| `engine.expert_cache_lab` | `validate`, `replay`, `predict` | Validated multi-request/layer trace, byte bounded LRU/LFU/original hybrid replay, causal atomic-group expert-set holdout |
| `engine.ssd_streaming_lab` | `plan`, `evaluate`, `read_fixture` | Bounded coalescing, declared read-cost replay, actual positional reads of owned temporary fixtures |

All tools accept a single `inputs` JSON object. Schemas and examples are in each bundle's `METHOD.md` and `fixtures/example.json`. Example: `Host(..., session_grants=['process.exec']).prepare(package)`, then `host.call(release, 'replay', {'inputs': fixture})`; successful native packets return `outcome: ok` and `outputs.result`.

The reusable SSD component exposes a caller-owned descriptor `BoundedPread`. Count and byte backpressure limit outstanding reads; cancellation invalidates work and prevents queued reads; short reads raise. Running POSIX pread cannot be interrupted, so close joins before the descriptor is closed. Tool access uses inline fixture data and an owned TemporaryFile only. Integration with a real expert store is an explicit subsequent embedding step; it is not engaged in any model runtime here.

## Primary source assessment

Pinned source revisions, API-reported licenses, primary README URLs and identity resolution are retained in each `SOURCES.json`. The curated awesome list is a discovery source, not independent support for performance. Upstream README statements below were inspected, not reproduced experimentally.

| Primary repository | Verified purpose relevant to these components | GB10 applicability limit |
|---|---|---|
| [MoE-Infinity](https://github.com/EfficientMoE/MoE-Infinity) | Activation-aware expert caching, request tracing and prefetch; README explicitly distinguishes public implementation from paper system | Reference policy ideas; PyTorch/CUDA installation and model path need separate validation |
| [DwarfStar](https://github.com/antirez/ds4) | Native selected-model engine, bounded SSD streaming, dedicated DGX Spark build documentation | Strong target-platform precedent; no integration or measured target result here |
| [moe-offload](https://github.com/Jakevin/moe-offload) | Experimental Apple Silicon MLX/llama.cpp expert offload and per-layer LRU | Cache strategy transferable; Apple MLX/Metal paths are not GB10 code |
| [InferSSD](https://github.com/wici-ai/inferssd) | llama.cpp-based SSD expert streaming; README includes a DGX Spark hardware row | Storage design relevant; advertised performance remains an upstream claim |
| [LayerStoRm](https://github.com/kkontosis/LayerStoRm) | Host-RAM-to-VRAM PCIe streaming for constrained consumer multi-GPU systems | Separate memory tiers and multi-GPU topology differ from unified-memory GB10; README marks predictive expert prefetch active work |
| [Strata](https://github.com/ro99/strata) | C++20/CUDA oversized-model engine; prediction may reorder work without changing routing | Useful routing invariant; named-engine identity alone proves no compatibility |

[MoE-Infinity paper](https://arxiv.org/abs/2401.14361) motivates request-level activation tracing. No upstream code was copied. LRU and LFU are standard policies; the density hybrid and simple transition predictor are original reference components, not reproductions of a paper system.

## Validation and limits

`tests/factory/test_research_cache_io.py` passed 11 CPU tests, including actual Host.prepare/call for all six capabilities. Independent checks cover known eviction sequences, variable byte bounds, oversize bypass, shared cross-request/layer identity, LFU versus LRU, future-suffix and current-group prediction invariance, frozen request holdout, request/layer transition isolation, duplicate range reconstruction, exact cost arithmetic, real short read, deterministic count/byte backpressure and cancellation. Each bundle also includes a runnable `verification.py` attached by `VERIFICATION-UNITS.json` and a CPU result attachment.

Run from the repository root:

```sh
PYTHONPATH=/home/user2/software-factory-spark-20261113/venv/lib/python3.12/site-packages:. /home/user2/rsi-expert-streaming-001/factory-env/bin/python -m pytest -q tests/factory/test_research_cache_io.py --no-cov
```

These local unit attachments are **CPU reference certification only**. Their local checker schema is deliberately not factory `cc_qualification` admission. No GPU execution, inference speedup, accuracy equivalence, real SSD throughput or production runtime engagement was measured. The 384 experts, 40 layers, six activated experts per layer workload is represented by events; actual expert sizes, dense weights, KV, scratch and OS headroom must be budgeted separately. Unified memory does not eliminate SSD transfer, and a separate PCIe H2D model must not be applied to GB10 without target evidence.
