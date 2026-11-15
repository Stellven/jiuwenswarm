# Heterogeneous placement and precision research capsules

Two standalone native CCv2 packages live under `jiuwenswarm/factory/ccs/`:

| Package | Callable tools | Executed implementation |
| --- | --- | --- |
| `heterogeneous_placement_lab` | `plan`, `execute_reference`, `overlap_schedule` | Shared-capacity measured-cost planner, actual stdlib selected-expert matrix-vector reduction, transfer/readiness schedule simulator |
| `precision_lab` | `quantize`, `evaluate`, `calibrate`, `memory_plan` | Actual custom INT4 pack/unpack, finite tensor error metrics, block-size calibration, weight and separate approximate KV storage |

Each ships `SKILL.md`, `METHOD.md`, `SOURCES.json`, `COMPONENT.json`, `VERIFICATION-UNITS.json`, fixtures, `EXAMPLES.json`, component source, native `run.py`, and standalone `verification.py`. EXAMPLES maps every capability to its complete `Host.call` inputs. The native process receives inline JSON, dispatches a fixed allowlist, and accepts no executable code, filesystem handles, or network requests. Input packet size and reference compute loops are bounded. No factory API or engine dispatch code is changed.

Qualification is **CPU reference only**. The reference matvec executes all six selected experts of the fixed 40-layer/384-expert topology and retains router coefficients. It is a projection/reduction oracle, not a complete MoE MLP or a heterogeneous CUDA implementation. Planner decisions are ordered greedy estimates from caller-supplied measurements; no optimality or measured GPU speed is claimed. The schedule is an optimistic simulation requiring independent engines and sufficient buffers. GB10 shares physical RAM: CPU/GPU allocation counts cannot be added as independent capacity. Explicit replicas and scratch consume that one budget.

Precision tooling is numerically approximate. The codec has low-nibble-first signed codes [-7,7], nearest-even rounding, float64 block scales, strict padding and malformed-code validation. It is deliberately distinct from native GGUF/EXL2 layouts. Exact and approximation gates are separate. Passing tensor error calibration proves neither language-model quality nor task correctness. KV payload estimates exclude format metadata and use conventional KV; DeepSeek MLA requires actual compressed cache layout. Separate weight-only and KV experiments before promotion.

Primary research was checked on 2026-11-14. SOURCES.json pins repository commit, README SHA256, URL and API-reported SPDX license for eleven repositories; papers/articles have explicit unpinned revision/license limitations. No upstream code or published speed ratio is copied.

| Primary source | Useful hypothesis or boundary |
| --- | --- |
| [KTransformers](https://github.com/kvcache-ai/ktransformers), [Fiddler](https://github.com/efeslab/fiddler) | Compare CPU expert compute plus activation movement against GPU weight movement; CPU ISA and GB10 support require independent checks. |
| [jjdna/litemoe](https://github.com/jjdna/litemoe), [ZhuLinsen/LiteMoE](https://github.com/ZhuLinsen/LiteMoE) | Different projects sharing the name; neither is silently equated with SenSys 2024 proxy-submodel tuning. |
| [mehbul/strata](https://github.com/mehbul/strata) | Measurement-driven placement is a candidate method; published AMD/Windows assumptions do not establish GB10 results. |
| [FlexGen/FlexLLMGen](https://github.com/FMInference/FlexLLMGen), [ZeRO-Inference](https://www.deepspeed.ai/2022/09/09/zero-inference.html) | Offload/overlap hypotheses are throughput and workload dependent; decode and batch measurements remain separate. |
| [AirLLM](https://github.com/lyogavin/airllm) | Layer streaming granularity differs from selected-expert execution. |
| [PowerInfer](https://github.com/Tiiny-AI/PowerInfer), [PowerInfer-2](https://arxiv.org/abs/2406.06282) | Activation sparsity/mobile methods need explicit model and hardware applicability; the latter paper is not a verified separate code release. |
| [ExLlamaV2](https://github.com/turboderp-org/exllamav2), [llama.cpp/ggml](https://github.com/ggml-org/llama.cpp) | Quantization/layout ideas require actual loader and matching ARM64/GB10 backend kernel validation. |

METHOD files define integration seams and invariants: router top-k capture; unchanged selected IDs/coefficients; expert kernel dispatch; event/buffer lifetime; weighted reduction; model load dtype/layout; KV writer/reader consistency; engagement counters; model correctness and hardware timing. Native symbol names must be located in the pinned checkout before patching. No runtime component patch, image build, GPU run or speed qualification is supplied by these packages.

Validation: `tests/factory/test_research_placement_precision.py` invokes every tool through a real CCv2 Host and checks capacity rejection, transfer-sensitive placement without selection changes, readiness scheduling, real nibble payloads, zero/extreme finite inputs, nonfinite rejection, malformed codec rejection, explicit approximation gates and tail-scale/KV storage accounting. Standalone verifiers provide additional directly runnable CPU checks. `VERIFICATION-UNITS.json` is a local evidence map, not a registration with the factory qualification service.
