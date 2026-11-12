# START HERE — Satay software factory demo (uses CCs)

**Repo / branch:** `Stellven/jiuwenswarm`, branch `cc-siminfeng` (descends from AI4Research-Main `141c1c4`; lab tools in submodule `lab/siminfeng`).
**What it shows (≈5 min):** plain llama.cpp + a task contract → JiuwenSwarm runs an agent that uses a few CCs (expert streaming, integration, build, lab, evidence) → an improved engine: **711.4 vs 841.5 ms/token (1.18×), identical output** (J-OM13 direct A/B). All results are recorded evidence; nothing is rebuilt or benchmarked during the talk.

## Run the demo (on Satay)
```sh
cd ~/projects/jiuwenswarm
export FACTORY_HOME=~/.jiuwenswarm-factory PATH=$PWD/.venv/bin:$PATH
jiuwenswarm factory demo preflight     # checks pack, assets, store, port
jiuwenswarm factory demo build         # ~20 s, assembles the offline pack from real evidence
jiuwenswarm factory demo serve         # http://127.0.0.1:8790, opens the browser
```
Controls (keyboard → ← space, or from a terminal): `jiuwenswarm factory demo {next,prev,pause,resume,goto N,status}`.

| # | Section | Evidence | s |
|---|---|---|---|
| 1–2 | Two slides: one token through the engine; the factory loop | slides | 30+30 |
| 3 | Plain llama.cpp `cf34d311` + the task contract | Run 4 records | 30 |
| 4 | JiuwenSwarm invoking CCs (material reads, cc_call receipts) | Run 4 telemetry | 35 |
| 5 | Source changes → built image | Run 4 commits + build receipts | 35 |
| 6 | Selected vs predicted experts, readiness | separate unscored capture J-XS4 | 35 |
| 7 | The agent changes its plan (CONFIG_MISSING → integrate reporting first) | Run 5 excerpt (held for later; kept nothing) | 40 |
| 8 | Result: 1.18×, identical output | J-OM13 (12-run A/B); Run 4 single runs | 35 |
| 9 | Handoff: `engine.expert_streaming` 2.0.0, tag `cc-rsi-v1` | RSI-START-HERE.md | 25 |

Rehearsed: all 9 sections advance on schedule (timed run 2026-11-12), total 295 s; every asset served (HTTP 200).

## Fallback (no browser/server)
```sh
less -R artifacts/factory/evidence/factory-bd173c082bf34ae3b8471938c19b8068/STORY.txt   # Run 4 story
less artifacts/factory/evidence/factory-53db494559954fc6a690a9a014afbf21/PLAN.txt         # Run 5 plan revisions
xdg-open ~/.jiuwenswarm-factory/demo-pack/assets/activity.html                           # expert activity
scriptreplay -t artifacts/factory/recording/evolve-run4.timing artifacts/factory/recording/evolve-run4.typescript -d 200
```

## The real end-to-end command (not run during the talk)
```sh
T=$(jiuwenswarm factory init jiuwenswarm/factory/tasks/rsi-small-fill.json)
jiuwenswarm factory run "$T" --grant process.exec --grant workspace.read --grant workspace.write --grant gpu.use
```
(~10 min per lab round with the fast contract `qwen36-quick-v1`.)

## RSI
Frozen CC baseline: tag **`cc-rsi-v1`** — see `RSI-START-HERE.md`.
