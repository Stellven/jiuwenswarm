# Ten-minute factory demo: task, revision, evidence

**Draft, 2026-11-12. This runbook supersedes the old Run-4-centred script in this file.** Start with exactly two opening slides, then show three moments: a task becomes capsule-backed engine work; evidence changes the next action; the result and reusable capsule pass to RSI. Run 5 is still running. TBD slots are preparation work, not claimed results.

Use the [opening deck](https://claude.ai/artifact/FedGTzXcaQ7YuNZJBQiuz2) for the two opening slides only. **TBD(DECK): confirm the two opening slide positions and an offline copy on the presentation machine.** The artifact could not be inspected from this drafting environment; the slide text below is a speaker cue, not a transcription of its contents.

## Before the clock starts

Use the existing runtime checkout and read-only views. Nothing is built, submitted, exported or replayed during this segment.

```sh
cd /home/muk/projects/jiuwenswarm
export PATH="$PWD/.venv/bin:$PATH"
export FACTORY_HOME="$HOME/.jiuwenswarm-factory"
export RUN4=factory-bd173c082bf34ae3b8471938c19b8068
export RUN5=factory-53db494559954fc6a690a9a014afbf21
export DOCS=/home/muk/projects/jiuwenswarm-cl
export B="$DOCS/artifacts/factory/evidence/$RUN4"
export OM=/home/muk/projects/siminfeng/experiments/jetson/OM
```

Screen labels describe the evidence: **LIVE** means a current read-only view of the running factory; **RECORDED** means an actual earlier run, transcript or receipt; **RECONSTRUCTED** means explanatory presentation material, never a live-agent or image result. A command reading an old run still shows recorded evidence.

| Time | Screen(s) | Purpose |
| --- | --- | --- |
| 0:00–1:30 | Two opening slides | Problem and factory contract |
| 1:30–2:15 | Baseline + real task brief | Start from identified plain llama.cpp |
| 2:15–4:30 | Capsule reads, `cc_call` receipts, source diff, build receipt | Moment 1: agent uses a CC |
| 4:30–6:30 | Inside the engine + changed decision | Moment 2: evidence revises work |
| 6:30–8:45 | Direct result, or labeled fallback | Moment 3: assess the result |
| 8:45–10:00 | Reusable capsule + RSI handoff | Carry evidence into the next segment |

The operator-verified pins are in the [real task brief](../../../jiuwenswarm/factory/tasks/expert-streaming-qwen36.json) and [frozen contract](../../../jiuwenswarm/factory/contracts/qwen36-bare-greedy-v1.json):

| Item | Pin |
| --- | --- |
| Model | Qwen3.6-35B-A3B UD-Q4_K_XL; 22,360,456,160 bytes (20.8 GiB); SHA256 `707a55a8a4397ecde44de0c499d3e68c1ad1d240d1da65826b4949d1043f4450` |
| Expert structure | 40 layers × 256 experts; 8 routed experts + shared; expert weights 18.3 GiB |
| Satay | Jetson Orin Nano Super 8GB; L4T R36.5.2; MemTotal 7.4 GiB |
| Baseline | `factory/llamacpp:bare-cf34d311`, `sha256:a9a0c71c08091badf3eb65cda3edc16a57387fd7151076b6dd197f13fe8ac3e6`; plain llama.cpp `cf34d311332e362198f0a410c466d1e940287d02` |
| Workload | `qwen36-bare-greedy-v1`; frozen greedy stdout `7a154179236463bc4c0628b2b24765bdebb6b51810885773b22359d7f2b608a8` |
| Agent | Codex workers: `gpt-6.1-sol`, reasoning effort `max`; Run 5 factory agent pinned with `JIUWENSWARM_CODEX_AGENT_EFFORT=max` (API-supported effort values span `none`…`max`) |

## Exactly two opening slides, 0:00–1:30

### Opening slide 1, 0:00–0:45 — the model is larger than memory

**Label: RECONSTRUCTED**, using operator-verified hardware/model facts.

```sh
xdg-open 'https://claude.ai/artifact/FedGTzXcaQ7YuNZJBQiuz2'
```

Show the first opening slide. **Say:** “This is a 20.8 GiB MoE model on a Jetson with 7.4 GiB of system memory; expert weights alone are 18.3 GiB. We are improving how the engine brings selected expert data to computation.”

### Opening slide 2, 0:45–1:30 — the agent chooses; the host enforces

**Label: RECONSTRUCTED**, explaining the current factory boundary.

```sh
xdg-open 'https://claude.ai/artifact/FedGTzXcaQ7YuNZJBQiuz2'
```

Keep the same deck open and advance once to its second opening slide; the command reopens the deck if needed. **Say:** “A real JiuwenSwarm agent uses Capability Capsules to inspect, integrate, build and measure, then revises its next action from evidence. The host keeps authority, image identity, job lifecycle and the frozen output contract intact.”

Leave the deck after this slide. The remaining screens are terminal evidence or the explicitly marked activity-view slot.

## Moment 1 — task → capsule use → built engine, 1:30–4:30

### Baseline and real task, 1:30–2:15

**Label: RECORDED** task inputs; this screen starts no inference.

```sh
cat "$DOCS/jiuwenswarm/factory/tasks/expert-streaming-qwen36.json"
```

**Say:** “The brief starts from working, plain llama.cpp `cf34d3113` and asks the agent to improve Qwen decode on Satay without changing the frozen output. It names resources, authority, `engine.expert_streaming@2.0.0` and a bounded budget, while leaving component choice and revision to the agent.”

### Capsule guide and material reads, 2:15–3:00

**Label: RECORDED** Run 5 material reads, alongside the current capsule source.

```sh
sed -n '1,70p' "$DOCS/jiuwenswarm/factory/ccs/expert_streaming/STREAMING.md"
cat "$DOCS/jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/component.yaml"
rg -n 'cc_material' "$FACTORY_HOME/sessions/$RUN5.jsonl" | less -S
```

**Say:** “The capsule gives the agent a guide, evidence method and component materials with dependencies, switches, engagement checks and rollback. The transcript shows actual material reads; displaying a source file alone would not establish that the agent read it.”

### Native calls and receipts, 3:00–3:35

**Label: RECORDED** Run 5 agent transcript.

```sh
rg -n 'cc_call|receipt' "$FACTORY_HOME/sessions/$RUN5.jsonl" | less -S
```

Show one `cc_call` request and its corresponding tool result/receipt, keeping the capability, key and outcome visible. **Say:** “These are recorded native capsule calls with receipts, connected to task evidence. A submission receipt establishes a durable attempt; the later result establishes completion.”

**TBD(CC-CALL-CUE):** select the exact request/result line pair and recording seek position for the talk; the transcript exists, but the presentation cut is not selected.

### Source diff and completed build receipt, 3:35–4:30

**Label: RECORDED** Run 5 integration and build, not a new build.

```sh
git -C "$FACTORY_HOME/agent-workspace/llama.cpp" show --stat 98d026ef19cfe040cd7da7a4d0692c45253aa1a9
git -C "$FACTORY_HOME/agent-workspace/llama.cpp" show 98d026ef19cfe040cd7da7a4d0692c45253aa1a9 -- | less
python -m json.tool "$FACTORY_HOME/artifacts/b6/b6ee941b3c394cc753c83cd646c2cf8bf04f13e35129a10ae8a76ce641ba1c23"
```

**Say:** “The source change is a named commit, and build `915b94fd95f04f73bc04db2a7503258d` has a completed receipt binding its request and build record to immutable image `sha256:74785dff…`. Source presence and a successful build do not establish a performance win.”

The receipt artifact is `915b94fd95f04f73bc04db2a7503258d:receipt`; its image ID is `sha256:74785dff355483f8185c0e7be0e340c530579dbfb29d3dc595a925e79503f9bb`.

## Moment 2 — inside the engine, then a changed decision, 4:30–6:30

### Activity and readiness, 4:30–5:15

**Label: RECORDED** separate operator Qwen run, J-XS2 smoke. **TBD(ACTIVITY-VIEW-PATH):** path to the actual engine activity view/capture and its seek position. Until it exists, show the recorded counters:

```sh
rg -n 'expert_readiness: stats decode_tokens=[1-9]' "$OM/J-XS2-smoke/001-base/stderr.txt"
less "$OM/J-XS2-smoke/REPORT.md"
```

**Say:** “In this separate smoke run, starting at 0% cached, 79% of selected experts were predicted and 82% of predicted bytes were ready before demand, versus 40% of unpredicted bytes. Over 63 decode tokens there were also 1.79 GB of duplicate demand reads and 2.23 GB of unused speculative reads: prediction quality alone is not readiness or speed.”

J-XS2's A/B report is `INVALID` (incomplete comparison/switch checks); these are descriptive counters from the completed Qwen arm, not an accepted A/B speed result. Its spec says carryover, with the recorded first-arm start at 0% resident; do not present a cold-versus-warm speed comparison. If an activity graphic is drawn from these counters, label that graphic **RECONSTRUCTED**.

### Evidence changes the next action, 5:15–6:30

**Label: LIVE** read-only plan/history view; the failure and repair are **RECORDED** Run 5 events.

```sh
jiuwenswarm factory story "$RUN5"
jiuwenswarm factory plan "$RUN5" --rev 12
jiuwenswarm factory plan "$RUN5" --rev 13
jiuwenswarm factory plan "$RUN5"
```

Point at **decision 13 / graph revision 13** in `Revision history`. **Say:** “The router-only image's effective-config probe failed `CONFIG_MISSING`, evidence `25ca171cbf99484bbadbbaa5a8698896`. The agent retained completed builds, added fill and pregate source with their performance switches off to obtain strict reporting, and deferred the router measurement until that repair was verified.”

The patch added `fill-integrate`, `pregate-integrate`, `config-stack-build` and `fill-measure`, and changed `router-measure` dependencies. Subsequent recorded strict probes passed with fill/pregate off; router measurement resumed at decision 16. The graph records work and lineage; it does not dispatch jobs or authorize acceptance. See [the design decision](DESIGN-CHANGE-2026-11-12.md) and [responsibilities](RESPONSIBILITIES.md) for the policy boundary; their older Run 5 slots remain placeholders.

## Moment 3 — result and reuse, 6:30–10:00

### Direct comparison, or the explicit fallback, 6:30–8:45

**Preferred label: RECORDED**, only when an actual J-OM15 direct comparison is available. **TBD(J-OM15):** exact result path, baseline/candidate image IDs and settings, cache protocol, complete direct comparison, correctness and verdict. No J-OM15 result was available when drafting; use the fallback now.

```sh
# Once J-OM15 is available, substitute its verified report path in this command.
# less 'TBD(J-OM15)'
jiuwenswarm factory status "$RUN5"
less "$B/STORY.txt"
less "$OM/J-OM13/REPORT.md"
```

For the fallback, label the status **LIVE** and the Run 4/J-OM13 results **RECORDED**. **Say:** “Run 5 is still running, so its final direct result is TBD. The fallback is Run 4's two single lab runs, plus the separate, direct J-OM13 comparison shown with its own conditions.”

| Evidence | Result | Scope |
| --- | --- | --- |
| Run 4 baseline → final | 903.95 → 785.22 ms/token: **13.1% less time per token; 15.1% more tokens/s** | One lab run per endpoint; byte-identical stdout; not a direct final ABBA |
| Run 4 `expert_fill`; `expert_pregate` | Kept at 1.11× and 1.13× in their respective incremental A/B comparisons | Do not multiply these ratios into a cumulative claim |
| Run 4 prerequisites | `mmap_advice` and `router_prefetch` dormant | Source retained, runtime switches off |
| Run 4 `thread_names` | Reverted under the **old** keep-only-performance-win rules | Current capsule acceptance assesses observability by signal + overhead; do not relabel the historical rejection |
| Prior direct ABBA J-OM13 | Stock 841.5 vs factory 711.4 ms/token, **1.18×** | Separate operator comparison; see `spec.json`, `REPORT.md`, `verdict.json` and per-run cache state |
| J-OM13 thread tuning | `-t 4`: 659.3 ms/token, **1.28×** versus stock | Separate tuning comparison, not the same-settings factory gain |

Snapshot at **2026-11-12T20:29:16Z**: Run 5 decision 19, graph revision 22, 9/40 turns; chunk-size tuning lab still running. Its completed fill trial was 962.42 vs 871.19 ms/token (ratio 1.1047), but A/A gap 0.2041, gate `null`, acceptance `reject`; this is not an accepted improvement. **TBD(RUN5-FINAL):** terminal outcome, selected source/image/config and direct final comparison. Recheck status at presentation time.

### Reusable capsule and RSI handoff, 8:45–10:00

**Label: LIVE** inventory/telemetry read; **RECORDED** evidence; the RSI improvement agenda is **RECONSTRUCTED** proposed work.

```sh
jiuwenswarm factory capsules --plain
jiuwenswarm factory telemetry "$RUN5"
less "$DOCS/docs/architecture/factory/RSI-HANDOFF.md"
```

**Say:** “The reusable object is the versioned capsule with its guide, components, acceptance rules and evidence, alongside the engine it helped build. RSI receives `factory.telemetry/1`, receipts and real improvement headroom; the earlier planted `Store.query` slowdown was removed from this baseline and is available only as a disclosed controlled seed.”

The current inventory is **16 capsules / 21 capabilities**, including **8 expert_streaming component entries**. Those entries are materials/patches, not eight independently executing services or proof that eight modules were enabled. The [RSI handoff](RSI-HANDOFF.md) records the version boundary and remaining work.

## Fallback when there is no live system

Use recordings under `artifacts/factory/recording/{evolve-run4,stream-run5}.*`, keeping the **RECORDED** label on screen. The Run 4 pair exists in this worktree; **TBD(RUN5-RECORDING):** make the `stream-run5.typescript` / `.timing` pair available and select the rev-13 seek interval. The requested Run 5 pair was not present here when drafting.

```sh
scriptreplay -t "$DOCS/artifacts/factory/recording/evolve-run4.timing" "$DOCS/artifacts/factory/recording/evolve-run4.typescript" -d 200
# Use only after the Run 5 recording pair is supplied:
# scriptreplay -t "$DOCS/artifacts/factory/recording/stream-run5.timing" "$DOCS/artifacts/factory/recording/stream-run5.typescript" -d 200
less "$B/STORY.txt"
less "$B/INDEX.md"
less "$B/source/f4530d71c9e4478e9d4ca881b8d65f2c.diff"
python -m json.tool "$B/artifacts/99951bdb8a3f9c5885ca931c4f1e4f4e52c8d452123b8dbc09a24c0acc30ae9a"
```

Use the Run 4 bundled diff/receipt for Moment 1 if the live home is unavailable. If no Run 5 capture is available, explain rev 13 from this runbook as **RECONSTRUCTED**, with the recorded evidence ID, rather than presenting it as captured execution. Use a prepared local copy of J-OM13 and J-XS2-smoke when the siminfeng checkout is unavailable; **TBD(OFFLINE-PACK):** confirm those files, the two opening slides and the activity capture on the talk machine. Reading a prepared bundle is sufficient; do not run export or replay during the demo. Any local web view must use port **5175**.
