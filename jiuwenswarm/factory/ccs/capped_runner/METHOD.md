# Capped runs without a shell

You cannot run commands. Everything that executes - an engine build, the checkpoint conversion, a requantization,
a server run, a paired accuracy run - is one `start` of a recipe here. The recipe builds the command line from your
arguments; flags, paths and environment variables outside what it allows are refused before anything runs.

Each run is a durable job of the task. After `start`, end your turn or do other reading: the controller waits while
the run is active and wakes you when it ends. Read `status` for progress (the last lines of its progress log) and,
once it ended, its result. The run's evidence is a host observation of kind `capped_run`
(factory.evidence.query kinds ["capped_run"]) with the request, the command, exit code, seconds, the memory cap, the
peak cgroup memory and the lowest available memory seen, plus the recipe's own result; its logs and result files are
artifacts `run-<attempt12>-<file>`. Cite that observation: it is written by the host, not by you.

Name the node (`node_id`) on every start. Builds count against the node's `build_attempts`, model loads against its
`gpu_launches`. Use a new `idem_key` for a new run; the same key returns the run already started.

## The machine gate and the cap

Every model load (convert, quantize, serve, accuracy) runs under
`systemd-run --user --scope -p MemoryMax=<cap> -p MemorySwapMax=0` (cap from the task, 96G by default) and starts only
when the machine gate passes: at least `need_available_gib` available (default 100 GiB) and no GPU process of another
user. While it fails the job waits and says so in its progress; after `gate_wait_s` it fails `MACHINE_BUSY`. A run
whose available memory drops under the floor (6 GiB) is stopped and fails `MEMORY_LOW`. `machine` shows the gate now.
Do not try to work around a closed gate: report it.

## Recipes (args)

- `build`: `{name, commit?, targets?, cuda?}`. Snapshots the owned checkout at `commit` (default HEAD) with git
  archive into builds/<name>/src and builds it: Release, CUDA arch 121-real, LLAMA_CURL off, at most the task's
  `build_jobs` jobs. Targets from llama-server, llama-quantize, llama-imatrix, llama-cli, llama-completion, llama-gguf-split,
  llama-bench (default server and quantize). A name is one commit; use a new name for a new commit. The result
  lists the binaries with sha256, the cmake flags and the files changed against the base commit (the build receipt).
- `convert`: `{name, commit?, outtype?, split_max_size?}`. Runs `convert_hf_to_gguf.py` of the owned checkout at
  `commit` on the task's `resources.checkpoint_dir` into packs/<name>/ (default --outtype bf16, --split-max-size 50G;
  NVFP4 blocks your converter keeps stay NVFP4). Checks free disk against the checkpoint size plus a 100 GB margin.
  Its log is the converter's output, so a timing projection your converter prints is in it.
- `quantize`: `{name, recipe, build, probe?, threads?}`. Runs the `argv` (or with `probe: true` the probe `argv`) of a
  weight pack compiler recipe with `llama-quantize` from `build`. Plan the recipe with `output` under
  packs/<name>/ and `recipe_out` in your workspace; run verify_recipe on it first. The probe times one layer:
  project the full time from it before you start the full run.
- `serve`: `{build, model, prompts?, server_args?, env?, trace?, n_probs?, repeat?, label?}`. Starts llama-server
  on `model` (a pack's first shard) with `-lv 4`, waits for health, sends each prompt greedily (temperature 0,
  seed 1, no prompt cache), stops the server. Prompts are `{id, text}`, `{id, path}` or `{id, jsonl}` (a file of `{"id", "prompt"}` lines, e.g. the calibration set; `limit` caps how many) with `template` raw (default)
  or muse_chat and `n_predict` (default 64). `server_args` from: -c -b -ub -np -kvu --cpu-moe --n-cpu-moe -ngl
  --moe-cache-mib --moe-cache-cpu-share -lm -fa -t -tb --no-warmup -ctk -ctv --seed. `env` takes LLAMA_* and
  GGML_* names (for example an engine switch). `trace: true` sets LLAMA_MOE_CACHE_TRACE to the run's trace.mct (the
  routing trace analysis.expert_routing_profile.rank_trace reads). With no prompts it only loads: the -lv 4 load log
  is the result. Rows (request, output_sha256, text_head, timings, top tokens with n_probs) are in rows.json.
- `accuracy`: `{name, arms: {A: {build, model, server_args?, env?}, B: {...}}, dataset_dir, stages?, margin_pts?,
  slots?}`. Paired MMLU as eval.paired_accuracy describes: one fixed seeded order, both arms on byte-identical
  prompts, next-token letter scored from 20 top log-probabilities, 32 questions per request. Stages default to
  B to 160, A to 160, B to 430, A to 430; the planned checkpoints are looked at as A advances and the run stops at
  the first decision. The state (accuracy/<name>/state.json) keeps every scored row: starting the same name again
  continues it. Its server logs are the -lv 4 logs eval.paired_accuracy.verify takes.

Choose arguments from the capsule methods and earlier evidence (for example the -b/-ub a prefill batch plan gives,
or the --moe-cache-mib of the lab recipe); the recipe does not choose them for you.
