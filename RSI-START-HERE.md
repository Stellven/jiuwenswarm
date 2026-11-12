# RSI START HERE — frozen CC baseline for the Satay software factory

**Baseline release:** tag `cc-baseline-2026-11-12` → commit `4fe167f9` on `Stellven/jiuwenswarm` branch `ai4r/iterative-cc-factory` (descends from AI4Research-Main `141c1c4`). This tag does not move. Improve CCs on your own branch from it.

**Companion pin:** lab tools come from `Muxite/siminfeng` (branch `main` = `jetson/c1`), commit `468d994` or later (`bin/jobq`, `cc/om_run`, `cc/abrun`, `cc/build_engine`). The factory finds it at `SIMINFENG_ROOT` (default `~/projects/siminfeng`).

## What is the CC under test
- `jiuwenswarm/factory/ccs/expert_streaming/` — `engine.expert_streaming` 2.0.0: guide (`STREAMING.md`), method (`EVIDENCE.md`), `SOURCE-MAP.md`, `ONTOLOGY.yaml` (provisional 0.1), 8 components (patches 01–11, 16) with `component.yaml` contracts, tools `applicability` and `engagement` (`run.py` → `jiuwenswarm/factory/expert_streaming.py`).
- Shared CCs it uses: `factory.builder`, `factory.engine_inspector`, `factory.lab_client`, `factory.evidence` (+ task graph `plan_get`/`plan_patch`), `factory.methodology_ab`, `factory.integration_skill`.
- List them: `jiuwenswarm factory capsules --plain`.

## Dependencies (Satay)
Jetson Orin Nano 8 GB, L4T R36.5.2, Docker with `--runtime nvidia` (run via `sg docker -c`), CUDA 12.6 at `/usr/local/cuda`, Python 3.12 venv `.venv` (uv), Codex CLI logged in (agent model gpt-6.1-sol), a running `bin/jobq worker` in siminfeng, model `~/models/campaign/qwen36-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (sha256 `707a55a8…4450`), baseline image `factory/llamacpp:bare-cf34d311` (`sha256:a9a0c71c…`).

## Invoke
```sh
export FACTORY_HOME=~/.jiuwenswarm-factory JIUWENSWARM_CODEX_AGENT_EFFORT=max PATH=/usr/local/cuda/bin:$PWD/.venv/bin:$PATH
T=$(jiuwenswarm factory init jiuwenswarm/factory/tasks/rsi-small-fill.json)
jiuwenswarm factory run "$T" --grant process.exec --grant workspace.read --grant workspace.write --grant gpu.use
jiuwenswarm factory story "$T"; jiuwenswarm factory plan "$T"; jiuwenswarm factory telemetry "$T"
```
Small representative task: `tasks/rsi-small-fill.json` (integrate expert_fill only, 1 build, 1 ABBA, ≤12 turns, ≤2 h; ~45–90 min wall on Satay).

## Evaluate a CC change
1. Offline, no GPU: `python -m jiuwenswarm.factory.replay <task_id> --capability <cap>` replays recorded read-only calls from Run 4 (`factory-bd173c082bf34ae3b8471938c19b8068`) against a disposable store copy and records per-call latency as `factory.telemetry/1`.
2. Unit: `.venv/bin/python -m pytest tests/factory --no-cov -q` (290 pass at the tag).
3. Engine components: `lab_client.ab_submit` ABBA under contract `qwen36-bare-greedy-v1` (frozen stdout `7a154179…`); acceptance per `component.yaml` (`performance`: gate improved; `observability`: signal delivered within 3% overhead). Runs that overlapped a compile are invalid (`host_contention`).

## What our segment established (do not redo)
Run 4 (recorded): plain 903.95 → 785.22 ms/token, single lab runs. Direct A/B J-OM13: plain llama.cpp 841.5 vs factory engine 711.4 ms/token (1.18×), identical output. Run 5: plan revision at rev 13; stopped at rev 21, kept nothing (held for later).

## Disclosure and headroom
The earlier planted Store.query slowdown is **not** in this baseline (local branch `rsi/controlled-seed-store-query` only, use only if disclosed). Genuine headroom: see `docs/architecture/factory/RSI-HANDOFF.md` (naive applicability ranking, evidence requirements not gating acceptance, non-atomic dispatch check, engagement ignores traces, no adaptive read policies, tool costs ~7.9 s config check / ~4.1 s preflight miss / whole-blob hashing on reads / multiple fsyncs on publish).
