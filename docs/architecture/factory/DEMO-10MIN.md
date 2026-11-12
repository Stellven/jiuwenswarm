# Automated ten-minute software factory demo

From `/home/muk/projects/jiuwenswarm-demo`, launch the offline presentation with this single shell command:

```sh
export PYTHONPATH=/home/muk/projects/jiuwenswarm-demo PATH=/home/muk/projects/jiuwenswarm/.venv/bin:$PATH; python -m jiuwenswarm.factory.cli demo build --pack /tmp/jiuwenswarm-demo-pack && python -m jiuwenswarm.factory.cli demo serve --pack /tmp/jiuwenswarm-demo-pack
```

The browser opens at **http://127.0.0.1:8790**. `xdg-open` failure is harmless; open the printed URL manually. This presentation uses the explicitly operator-requested port 8790. It starts no model, inference, build, Docker container or GPU work. Build here means copying and formatting evidence. The factory store and siminfeng checkout are read-only. The launch above writes the pack to `/tmp`; the CLI's default pack location is `~/.jiuwenswarm-factory/demo-pack` when used in an environment that permits writing there. `--home` selects a different store; `build --siminfeng PATH` selects a different lab checkout.

Once built, the pack is self-contained: HTML, inline slides, activity capture, contract, current brief, frozen stdout, source diffs, build requests/receipts, record snapshots, selected transcript request/result pairs, before/after plans, J-OM13 report and backup documents are local files. No external fonts or network services are needed. Copy the directory and run `serve --pack PATH` with this checkout installed. Serving recorded sections does not require the original store. Missing evidence is printed as `GAP` at build time and displayed in the page; preflight fails on gaps.

The server owns the clock, so browser refreshes and terminal controls share state. It auto-advances and pauses at the end. Editing **`sections.json`** in the pack changes durations and content; restart `serve` to load edits. Its `budget` is 600 seconds by default. The elapsed budget counts active presentation time; pauses stop it, while manual navigation restarts only the section timer. Backup links open outside the timed flow.

| Section | Default duration | Evidence and label |
| --- | ---: | --- |
| 1. Engine opening slide | 45s | `demo/assets/slides/engine.html`; RECONSTRUCTED explanation |
| 2. Factory opening slide | 45s | `demo/assets/slides/factory.html`; RECONSTRUCTED explanation |
| 3. Baseline + contract | 45s | Run 4 task and bare evaluation; `contracts/qwen36-bare-greedy-v1.json`, hash-matched frozen stdout; `tasks/expert-streaming-qwen36.json` current brief; RECORDED |
| 4. JiuwenSwarm invoking CCs | 65s | Run 4 material/call telemetry, matched `cc_call`/material transcript request/result pairs; RECORDED |
| 5. Source + build receipts | 70s | Run 4 expert_fill / expert_pregate build observation → request → pinned integration commit diff → build record and receipt → immutable image ID; RECORDED |
| 6. Expert activity | 55s | `siminfeng/experiments/jetson/OM/J-XS4-activity/{activity.html,stderr.txt,image.id}`; SEPARATE CAPTURE, unscored `factory/llamacpp:xs-trace` |
| 7. Evidence-driven revision | 75s | Run 5 decision 13 and cited evidence; existing taskgraph replay of graphs 12 and 13; RECORDED excerpt |
| 8. Result + generated text | 125s | `siminfeng/experiments/jetson/OM/J-OM13/REPORT.md`, Run 4 single-run evaluations, frozen stdout; RECORDED |
| 9. Capsule handoff | 75s | `engine.expert_streaming` 2.0.0 manifest; `RSI-START-HERE.md`, tag `cc-baseline-2026-11-12`, commit `4fe167f9`; RECORDED |

Run 4 is `factory-bd173c082bf34ae3b8471938c19b8068`; Run 5 is `factory-53db494559954fc6a690a9a014afbf21`. The activity caption compares selected and predicted experts: 92% of predicted vs 55% of unpredicted expert bytes ready before demand; 79% predicted, calculated from the recorded readiness counters. This is a separate unscored capture, not the J-OM13 performance trial. The original activity HTML's unknown fields remain visible as recorded.

Run 5's router-only image failed `CONFIG_MISSING`; decision 13 integrated source 03–08 with switches off to obtain strict reporting and moved router measurement after the rebuilt image. Run 5 was held for later and kept no component. The page distinguishes J-OM13's 12-run ABBA (plain 841.5 vs factory engine 711.4 ms/token, 1.18×, identical output) from Run 4's single lab runs (903.95 → 785.22 ms/token). Neither read-only command execution nor graph replay is represented as a new live-agent run.

Use the arrow keys or page buttons to advance, and space to pause/resume. The section picker and terminal `goto` are **one-based**. Claude can drive the same server from another terminal:

```sh
jiuwenswarm factory demo status
jiuwenswarm factory demo next
jiuwenswarm factory demo prev
jiuwenswarm factory demo pause
jiuwenswarm factory demo resume
jiuwenswarm factory demo goto 7
jiuwenswarm factory demo live
```

Use `--port N` on both `serve` and control commands only if explicitly changing the presentation port. `GET /api/state` supplies browser polling; `POST /api/control` accepts JSON such as `{"action":"goto","section":7}`. `serve --no-open` suppresses browser launch. Stop the server with Ctrl-C.

`live` executes the real, read-only factory CLI in the server's Python environment (15-second timeout): `capsules --plain`, `story RUN4 --plain`, or `plan RUN5 --rev 13`, selected by the current section. Its output is labelled **LIVE** as a current invocation, with historical evidence still **RECORDED**. If the invocation fails or times out, the page shows the same command's output captured during build, labelled **RECORDED FALLBACK**, together with the failure reason. No controller or model is invoked. These live reads are optional; the timed flow always has its copied evidence.

Before serving, check readiness:

```sh
jiuwenswarm factory demo preflight --pack /tmp/jiuwenswarm-demo-pack
# Optional read-only local image check, only where Docker access is permitted:
jiuwenswarm factory demo preflight --pack /tmp/jiuwenswarm-demo-pack --images
```

Preflight prints PASS/FAIL for the pack, copied asset hashes, evidence gaps, free port, readable store, both task IDs and the real entrypoint. Image inspection is skipped by default; `--images` uses only `sg docker -c 'docker image inspect …'`. A running server intentionally fails the free-port check. Preflight needs the original store even though the recorded presentation does not.

Every section exposes provenance links with task/record IDs, original file paths, copied assets and image IDs where applicable. Source diffs come from the checkout pinned in the stored build request, or the existing sanitized evidence export if that checkout is unavailable. Backup views are the source map, ontology, design-change decision, responsibility map and Run 4 full story. The real `init … && run … --grant …` command remains visible throughout, explicitly **not executed during the talk**.

Requested checks:

```sh
PYTHONPATH=/home/muk/projects/jiuwenswarm-demo /home/muk/projects/jiuwenswarm/.venv/bin/python -m pytest tests/factory/test_demo.py tests/factory/test_views.py --no-cov -q
```
