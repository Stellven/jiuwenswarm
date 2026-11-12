# Ten-minute CC demo: an agent grows an inference engine

**One sentence:** A Codex agent inside JiuwenSwarm receives a bare llama.cpp and five engine components packaged as CCs. It works out the dependency order itself, integrates each component, builds it, A/B-tests it on a 35B MoE model on an 8 GB Jetson, keeps or rejects it, and finishes with a faster engine whose output is byte-identical to the reference. The run took 175 minutes, with 15 agent turns and 25 decision revisions. No human touched it.

Everything shown is a recording or read-only evidence from that run. Nothing is rebuilt during the talk.

```sh
export FACTORY_HOME=$HOME/.jiuwenswarm-factory
export T=factory-bd173c082bf34ae3b8471938c19b8068
export B=artifacts/factory/evidence/$T     # slim committed bundle (records, story, small artifacts)
```

## The result (one screen)

| Image | ms/token (n=1 lab run) | tok/s | output |
|---|---|---|---|
| bare llama.cpp `cf34d311` | 903.95 | 1.11 | `7a154179…` = reference |
| grown engine (expert_fill + expert_pregate) | 785.22 | 1.27 | `7a154179…` = reference |

| Component | A/B (2 ABBA rounds; A/A noise) | Agent decision |
|---|---|---|
| mmap_advice | 0.49× (A/A 0.06) | **dormant**: rejected, switch off, code kept because later components need it |
| router_prefetch | 0.62× (A/A 0.09) | **dormant**: same |
| expert_fill | **1.11×** (A/A 0.03) | **keep** |
| expert_pregate | **1.13×** (A/A 0.02) | **keep** |
| thread_names | 1.01×, gate `not_measured` | **revert**: observability only, no performance win, nothing depends on it |

The agent declined to claim a cumulative speedup. Its final handoff says "incremental ratios are not multiplied into a cumulative claim". The 1.15× bare→final comparison above is the operator's comparison of two single runs, and is labeled as such.

## Running order

| Time | Show | Point |
|---|---|---|
| 0:00–1:00 | `ls jiuwenswarm/factory/ccs/expert_streaming/components/`, then `cat jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/cc.yaml` | **A component is a CC.** It is a patch plus a contract: `depends_on`, switches, engagement checks and rollback. Adding a component means adding a folder; nothing is wired in code. |
| 1:00–2:00 | `cat jiuwenswarm/factory/ccs/methodology_ab/AB.md`, then `cat jiuwenswarm/factory/tasks/evolve-qwen36.json` | **A methodology is a CC too.** The A/B procedure (ABBA, A/A noise floor, keep only on improvement, byte-identical output) is material the agent reads, not code it calls. The task is one paragraph plus a budget. |
| 2:00–3:00 | `scriptreplay -t artifacts/factory/recording/evolve-run4.timing artifacts/factory/recording/evolve-run4.typescript -d 200` (first screen) | **Start it and walk away.** `jiuwenswarm factory run $T --grant …`. Grants are explicit, and the controller refuses to run a task that needs effects without them. |
| 3:00–5:30 | `jiuwenswarm factory monitor --port 8787` → browser `?task=$T` | **Watch it think.** Engine-stack bars, the chain links, decision timeline, and the live job log tail. Point at rev 6, `keep_dormant`. The agent rejected mmap_advice (0.49×), yet saw that router_prefetch, expert_fill and expert_pregate need its code. It kept the code with the switch off and checked that claim against the declared dependency graph. |
| 5:30–7:30 | `less -R $B/STORY.txt` (or `jiuwenswarm factory story $T`) | **Each step is evidence.** Every line comes from the store: a commit, a durable build (about 130 s, survives turn end), a Manager admission of the exact image ID, an A/B with A/A noise, a byte-identical contract check, and a decision citing that evidence. Revs 14 and 18 keep; rev 22 reverts thread_names: "naming engagement passed but is not a performance win". |
| 7:30–8:30 | `cat $B/INDEX.md`; `jiuwenswarm factory export $T --out /tmp/run4 && python -m jiuwenswarm.factory.export --verify /tmp/run4` | **The chain is connected.** It runs component → commit → build → image → admission → lab → evaluation. The full export verified 604 files with a clean secrets scan. The repository copy is slim: files of 1 MiB or more are listed with their hashes in `SLIM-OMISSIONS.json`. |
| 8:30–10:00 | `jiuwenswarm factory telemetry $T`; `docs/architecture/factory/TELEMETRY.md` | **Handoff to RSI.** Every CC call, material read, agent turn, job transition and decision is a `factory.telemetry/1` event. `replay` re-runs read-only calls against a copy of the store. The RSI system takes it from here: the factory leaves the data, and finding what to improve is the next presenter's job. |

## Honest failures worth showing (not hidden)

Earlier runs are kept as evidence, not deleted:
- **Run 1** (`7ff26321`) was launched without grants and burned its budget. The fix is the controller refusal shown above.
- **Run 2** (`fe255fce`) failed with `API_FAILED`, because the sealed interpreter lacked the venv. The fix is `FACTORY_PYTHON`.
- **Run 3** (`f0a3c6c0`) correctly rejected mmap_advice, but could not proceed because its dependents needed the code. The fix is the `keep_dormant` decision, with dependency checking.

Every fix was a tool or capsule change by the operator. The agent's judgement was right each time, and the tools were what improved. That is the case for RSI.

## Recordings

`artifacts/factory/recording/evolve-run{1..4}.{typescript,timing}` contain terminal output from `script -T`. Run 4 is the demo; the others are the failure history. The earlier fixed-patch demo (`demo-run1/2`, K=48 → K=8 config repair) is described in RUNBOOK.md and COMPLETION-REPORT.md.
