# Outside sources and how to switch them

The factory code runs from this repository alone. Everything outside it (a lab checkout, engine sources, model files, a remote lab) is reached through one environment variable each, with a default. A different lab, engine fork or model location needs no code change.

## The lab kit

The host-side lab tools the factory drives ship in the package, under `jiuwenswarm/factory/labkit/`:

| Tool | Path in the kit | Used by |
|---|---|---|
| Job queue (flock-serialized, durable) | `bin/jobq`, `bin/run_op` | `jobs.py` for every build and lab job |
| A/B runner and gate | `cc/abrun/` | `ab.py`, `ab_runner.py` |
| Image builder (llama.cpp CUDA images) | `cc/build_engine/build_engine.py`, `builds/` | `builder.py`, `build_job.py` |
| Guarded engine run with watchdog and samplers | `cc/om_run/om_run.sh`, `cc/resource_observe/`, `cc/thread_sampler/`, `cc/page_cache/` | `lab_runner.py` |

These were copied from the Satay lab repository (`Muxite/siminfeng` at `45813e3d`), which otherwise holds experiment records and logs. Its tests now live in `tests/factory/labkit/`.

| Variable | Default | Meaning |
|---|---|---|
| `FACTORY_LAB_ROOT` | the bundled `labkit/` | another checkout with the same layout (`SIMINFENG_ROOT` is still read) |
| `FACTORY_LAB_STATE` | `~/.jiuwenswarm-factory/lab` | writable lab state: the job queue (`jobq/`), run logs, preflight cache |
| `FACTORY_JOBQ_BIN`, `JOBQ_DIR` | from the two above | one tool or the queue directory alone |
| `FACTORY_BUILD_ENGINE`, `FACTORY_BUILD_RECIPE`, `FACTORY_OM_RUN`, `FACTORY_ABRUN` | from the lab root | one tool alone |
| `FACTORY_BASELINE_RECORD`, `FACTORY_REFERENCE_RECORD` | `<lab root>/cc/build_engine/results/...` | Jetson reference build receipts. These are site records, not code, so the bundled kit has none; set them when freezing a Jetson reference. |

An external lab checkout keeps its queue at `<lab>/lab/jobq`, so factory jobs share it with the lab's other jobs on that host.

## Engine sources, packs and models

Task files name sources through `${FACTORY_...}` references that the factory expands when it loads a task (`expand_sources` in `jiuwenswarm/factory/config.py`, which lists every variable with its default in `SOURCE_DEFAULTS`):

| Variable | What it names |
|---|---|
| `FACTORY_LLAMA_SOURCE` | the clean stock llama.cpp checkout that builds start from |
| `FACTORY_LLAMA_CMAKE_CACHE` | the CMake cache of the stock native CUDA build |
| `FACTORY_MODELS` | the model root holding the campaign GGUF files |
| `FACTORY_STRATA_PACK`, `FACTORY_STRATA_SOURCE` | the Strata DeepSeek pack and engine source tree |
| `FACTORY_ONE_SHOT` | the capped one-shot runner the capsule parity helpers call |
| `FACTORY_OVERLAP_WATCH_RUN` | the control run allowed to hold the GPU during an overlapping native build (no default) |

Recorded contracts (`contracts/*.json`) keep the paths they ran with, because their digests are part of the record.

The Strata engine is one of the engines the factory can measure. Nothing in the factory clones it: its source tree and pack are inputs named by those variables, and `/opt/strata/` is only the install path inside an engine image.

## A remote lab

The lab mailbox is a directory or an HTTP address. With `FACTORY_LAB_MAILBOX=http://host:8790` and a token, the lab manager and any lab agent can run on different machines. See [LAB-MANAGER.md](LAB-MANAGER.md).
