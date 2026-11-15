# Working Strata profile and llama.cpp fallback

Both paths now produce output on this GB10 through the shared factory queue.

## What went wrong

The original Strata launch profile was too aggressive for unified memory. The
CUDA runtime and compiled engine worked; loading exhausted host headroom before
the engine became ready. The collector stopped it at 7.72 GiB available, while
the container cgroup reported only 10.17 GiB charged. GPU memory was therefore
not fully represented by that cgroup ceiling.

Source inspection explains the risky defaults: `vram_experts=1.0`, only 600 MiB
reserved per GPU, automatic CPU expert caching, and a 16,384-token prefill chunk.
The loader estimates GPU placement and host caching separately, using memory
estimates made before expert uploads. On GB10 they consume the same physical
RAM. This explains the observed pressure; it is not an isolated proof that any
one allocator alone caused the entire deficit.

## Strata recovery

The immutable engine and model files are unchanged. The explicit profile in
[configs/strata-conservative.json](configs/strata-conservative.json) uses:

- 1,024 context and a 256-token prefill chunk.
- Half of the GPU expert budget, with 32 GiB reserved per GPU and explicit UMA
  headroom. The resulting placement logged 25.70 GB of GPU experts and 6.58 GB
  of dense weights; remaining experts are read from the model files.
- CPU expert memory mapping, automatic RAM store/copy and expert cache disabled,
  four CPU threads, two Engram reader threads and a 64 MB Engram cache.
- All six experts per token, DSpark disabled, and a read-only expert profile.

The successful attempt `5f4aeac8fba04610ab19913d3831e9a3` loaded, reached `READY`,
generated 32 tokens, returned `DONE ... length`, and exited 0. Whole collector
runtime was 67.60 seconds. Minimum sampled host available memory was 81.48 GiB;
peak sampled cgroup current was 71.43 GiB, including reclaimable file pages.
There was no guard violation; the container was quiescent and removed.

Actual output:

> Watering in the morning gives plants time to absorb moisture before the heat of the day causes it to evaporate. It also reduces the risk of fungal diseases,

The trailing comma is the fixed 32-token limit. This is a functional smoke,
not a performance or general accuracy benchmark. The original failed attempts
remain intact. Full DeepSeek weight hashes were not recomputed: matching sizes
and timestamps do not establish full content verification. Small pack and
configuration files remain SHA-256 pinned.

The factory smoke now defaults to this proven conservative profile. Start the
finite bridge, submit, and inspect the attempt separately:

```sh
deploy/spark/start-bridge.sh
# In another terminal:
deploy/spark/factory-container.sh deploy/spark/submit-smoke.py
```

The limit remains eight CPUs, 104 GiB container memory, zero additional swap,
32 generated tokens, an 8 GiB host guard, and a ten-minute smoke deadline.
The host guard remains necessary on this hardware. The original host Strata
configuration was preserved; it was not silently replaced.

## Usable llama.cpp fallback

```sh
/home/user2/software-factory-spark-20261113/sources/cc-dgx-spark/deploy/spark/run-stable.sh \
  'What is 9 multiplied by 7? Reply with only the number.'
```

This exact command produced `63`. It starts a finite bridge if needed, submits
a durable GPU job, waits for the recorded result, and cleans up any bridge it
started. It leaves an already-running bridge alone. It installs no server.

The fallback is **llama.cpp with the existing GPT-OSS 20B MXFP4 model**, rather
than DeepSeek. It reuses the successful native CUDA 13 / SM121 build from source
`cf34d311332e362198f0a410c466d1e940287d02`. Packaging only adds target labels;
no recompilation is claimed, and the executable/image layers are verified
against the earlier build receipt. The model's complete local SHA-256 was
verified before execution:
`27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`.

Qualification `015dae68de67465994b61ea9d895f807` ran three separate GPU containers:

1. `17 + 25` → `42`.
2. Computer components → `CPU, memory (RAM), and storage (hard drive/SSD).`
3. The same arithmetic prompt → the identical `42` output.

All three exited 0 and were removed. Direct device-process observations matched
their container cgroup PIDs and recorded about 11–12 GiB of GPU allocation.
An initial qualification wrapper incorrectly required an offload log line that
this build suppressed; that failed assessment is preserved separately. The
working gate uses owned GPU process measurements and the CUDA backend identity,
not that optional log wording.

Fallback runs use eight CPUs, 24 GiB container memory, zero additional swap,
32 generated tokens, a five-minute execution deadline and the same 8 GiB host
memory guard. Inference and builds stay serialized in the shared queue. This
is bounded functional qualification, not a long-running load or concurrency
certification. No model downloads, global packages or driver changes were needed.

`results/recovery-summary.json` records final identities, observations, tests and
cleanup. Raw outputs, telemetry, inspected limits and executed worker sources
are durable factory artifacts under `port-store/runs/` and
`port-store/runtime-jobs/`.
