# Spark native factory builds

Source `ops/spark/env.sh` before using the factory CLI. The default external
siminfeng checkout and job queue are absent on this machine. The copied queue
in `vendor/jobq` has its exact source digest recorded in `vendor/PROVENANCE.json`.
The private `~/predemo-spark/OPS/jobq-cpu` queue accepts only CPU/build classes
through `bin/cpu-run-op`; GPU-class work is refused. No existing host queue is
modified. The lead engineer decides when to start `bin/factory-cpu-worker` so
builds do not overlap measured inference.

Prepare a capsule's isolated source and evidence store without launching an
agent, model or build:

```
.venv/bin/python scripts/spark/prepare_star_home.py observability_event_recorder
```

This creates a clean isolated local clone at the stock pin, initializes the Spark task,
attaches raw/readable contracts, owner ontology and capsule materials, and
copies the existing Codex auth into that home's private profile. Auth content
is never copied to evidence. `preparation.json` labels this as preparation.

A native Builder request uses the existing durable build API with:

```
{
  "target": "spark-gb10",
  "build_target": "llama-server",
  "delivery": "native",
  "native_cmake_cache": "/home/user2/predemo-spark/build-stock-cuda121/CMakeCache.txt",
  "source": {"path": "<owned checkout>", "commit": "<clean committed revision>"},
  "dependency": {"path": "/home/user2/predemo-spark/llama.cpp-stock", "commit": "9048bad8d6e3a0f9f1726e238e451181c7e02613"},
  "tag": "factory/llamacpp:star-recorder",
  "deadline_s": 5400
}
```

The existing Spark worker snapshots committed source, compiles with the pinned stock CMake cache generator, compiler paths and
GGML/LLAMA options (including native CPU kernels and SM121), at most eight parallel build jobs, retains linked local
libraries, and returns a digest-verified native executable receipt. No runtime
image is created for `delivery=native`. The existing default image delivery
and image-admission checks remain available and unchanged. A native receipt
cannot be admitted as an image by the factory lab.

All inference uses the separately reviewed `bin/capped` wrapper under the lead
engineer's control. `star-deepseek-v1` explicitly blocks factory lab launches.
The factory source-integration agent must not start any model process. The
small-fixture scorer and DeepSeek parity/activation results are imported from
the capped lane, with source-only and build-only evidence labelled distinctly.
