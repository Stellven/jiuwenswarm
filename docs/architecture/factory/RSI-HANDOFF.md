# Factory → RSI handoff

**Draft, 2026-11-12.** This is the handoff for the factory segment in [DEMO-10MIN.md](DEMO-10MIN.md). Run 4 is recorded evidence; Run 5 is still running. Measurements, source/catalog availability and proposed improvements have different status throughout this note.

## Version boundary

| Item | Boundary |
| --- | --- |
| Baseline branch | `cc-siminfeng` |
| Handoff tag | `cc-baseline-2026-11-12` |
| Exact baseline commit | **tag `cc-baseline-2026-11-12` (resolve with `git rev-parse cc-baseline-2026-11-12`)**; the tag ref was absent in the local checkout when drafting. Resolve and record the tag's commit before a baseline/revision comparison; no tag is created by this docs task. |
| This documentation worktree | `/home/muk/projects/jiuwenswarm-cl`, branch `ai4r/contract-loop` |
| Factory agent capsule | `engine.expert_streaming@2.0.0`; record capsule version/tree hash and host-code revision with each later comparison |
| Run 4 | `factory-bd173c082bf34ae3b8471938c19b8068` |
| Run 5 | `factory-53db494559954fc6a690a9a014afbf21`; in progress at 2026-11-12T20:29:16Z, decision 19 / graph revision 22 |

Codex workers use `gpt-6.1-sol` with reasoning effort `max`, within the API-supported `none`…`max` range. Run 5's factory agent is pinned by `JIUWENSWARM_CODEX_AGENT_EFFORT=max`; keep that setting in comparison provenance rather than assuming a default.

The host enforces authority, identity, contracts and lifecycle; the agent chooses actions. Native CCs remain trusted-local code. The feature-scoped [amendment](AMENDMENT.md) and [design decision](DESIGN-CHANGE-2026-11-12.md) apply; this handoff introduces no M1 runtime, intent compiler, planner service or RSI console.

## What the factory segment established

- A real agent used capsule materials and native calls to integrate source, build identified engine images, measure against a frozen output contract and retain negative evidence. Run 4's [story](../../../artifacts/factory/evidence/factory-bd173c082bf34ae3b8471938c19b8068/STORY.txt), [decisions](../../../artifacts/factory/evidence/factory-bd173c082bf34ae3b8471938c19b8068/records/decisions.json) and [evidence index](../../../artifacts/factory/evidence/factory-bd173c082bf34ae3b8471938c19b8068/INDEX.md) are the recorded chain.
- Run 4's endpoint lab runs measured 903.95 → 785.22 ms/token (13.1% less time/token, 15.1% more tokens/s), one run each. It kept `expert_fill` (1.11×) and `expert_pregate` (1.13×) in incremental comparisons, kept mmap/router source dormant, and reverted `thread_names` under the old performance-win rule. Current observability acceptance uses signal + overhead; that policy does not rewrite old results.
- Prior direct ABBA J-OM13 measured stock 841.5 vs factory 711.4 ms/token (1.18×); 659.3 ms/token with `-t 4` (1.28×) is a separate tuning comparison. Evidence is `/home/muk/projects/siminfeng/experiments/jetson/OM/J-OM13/{spec.json,REPORT.md,verdict.json}` and its per-run files. Final Run 5/J-OM15 results remain **TBD**, and successive ratios are not multiplied.
- In Run 5, a router-only image's strict probe failed `CONFIG_MISSING`, evidence `25ca171cbf99484bbadbbaa5a8698896`. Decision 13 / graph revision 13 added source-only fill/pregate work and a config-stack build, retained completed builds, and deferred router measurement. Later probes passed with fill/pregate off, and router measurement resumed at decision 16. `factory story` and `factory plan --rev 13` expose the lineage.
- The separate operator J-XS2-smoke Qwen arm began at 0% cached and measured 79% of selected experts predicted, predicted bytes 82% ready before demand versus 40% for unpredicted bytes, plus 1.79 GB duplicate demand reads and 2.23 GB unused speculative reads over 63 decode tokens. Read `/home/muk/projects/siminfeng/experiments/jetson/OM/J-XS2-smoke/001-base/stderr.txt` and `REPORT.md`: the A/B report is `INVALID`, so these counters establish mechanism observations, not a speed win. The declared protocol is carryover; the first arm happened to start at 0% resident.

The workload is Qwen3.6-35B-A3B UD-Q4_K_XL, 22,360,456,160 bytes (20.8 GiB), SHA256 `707a55a8…4450`; 40 layers × 256 experts, 8 routed + shared, 18.3 GiB expert weights. Satay is Jetson Orin Nano Super 8GB, L4T R36.5.2, MemTotal 7.4 GiB. The [task](../../../jiuwenswarm/factory/tasks/expert-streaming-qwen36.json) pins plain llama.cpp `cf34d3113`, baseline image `factory/llamacpp:bare-cf34d311` / `sha256:a9a0c71c…`, and contract `qwen36-bare-greedy-v1` with frozen stdout `7a154179…`. Use the full pins from the task/contract in any comparison.

## Capsule inventory: catalog entries versus execution

Read-only inventory command, from the existing runtime checkout:

```sh
cd /home/muk/projects/jiuwenswarm
FACTORY_HOME="$HOME/.jiuwenswarm-factory" .venv/bin/jiuwenswarm factory capsules --plain
```

Observed inventory: **16 capsules / 21 capabilities / 0 adapters**, including **8 expert_streaming components**. The older catalog's **9-capsule/12-module** count is dated and is superseded for this snapshot.

| Inventory group | Entries | Meaning |
| --- | --- | --- |
| Executable native bindings | `factory.builder` (4 capabilities), `factory.engine_inspector` (3), `factory.evidence` (5), `factory.lab_client` (7), `engine.expert_streaming` (2) | Five native capsule bindings expose the 21 callable capabilities. The streaming capsule's applicability/engagement tools inspect and publish observations; inference executes in identified lab images. |
| Expert-streaming component entries | `mmap_advice`, `router_prefetch`, `expert_fill`, `expert_pregate`, `thread_names`, `expert_readiness`, `inflight_join`, `phase_stats` | Eight material-only component capsules: patch/source dependencies, runtime switches, evidence and acceptance declarations. Catalog presence does not mean integrated, built, enabled or measured. |
| Other material-only entries | `factory.engine_component`, `factory.integration_skill`, `factory.methodology_ab` | Reference component, integration skills and A/B methodology; readable material grants no execution authority. |

The five native and eleven material-only entries total sixteen. Distinguish executable factory tool code from engine components that become executable only after integration/build and appropriate enablement. Source dependencies can be present with their switches off. `p12`–`p15` below are candidates outside these eight current component entries.

## Telemetry and evidence locations

Default home: `$HOME/.jiuwenswarm-factory` (override `FACTORY_HOME`). Preserve task IDs, attempt IDs and full hashes when passing evidence across segments.

| Location / view | Contents and limits |
| --- | --- |
| `$FACTORY_HOME/telemetry/events.jsonl` | `factory.telemetry/1`: `cc.call`, observed `cc.material`, `agent.turn`, job transitions, decisions, build/lab/evaluation events; capsule/version/release hash, duration, bytes, outcome and available evidence metrics |
| `$FACTORY_HOME/telemetry/errors.jsonl` | Failed telemetry emissions; missing events/fields are not successful zero-cost operations |
| `jiuwenswarm factory telemetry TASK` | Read-only summary of call distributions, turns and job timing; overlapping spans must not be added as independent CPU costs |
| `$FACTORY_HOME/factory.sqlite` | Task-scoped evidence, versioned decisions/graph patches, attempts, evaluations and artifact references; retain matching blob/store snapshots for offline comparisons |
| `$FACTORY_HOME/artifacts/<prefix>/<sha256>` | Evidence bytes; artifact records bind IDs to hashes, sizes and producer attempts |
| `$FACTORY_HOME/sessions/TASK.jsonl` | Recorded agent/tool stream, including available guide/material reads and `cc_call` results; a shell read alone is not an observed `cc.material` event |
| `$FACTORY_HOME/ccstore/calls.sqlite` and `ccstore/artifacts/` | CC-v2 call/receipt state and artifacts; correlate receipts with task records and durable attempts |
| `artifacts/factory/evidence/factory-bd173c082bf34ae3b8471938c19b8068/` | Existing slim Run 4 export bundle: `INDEX.md`, `STORY.txt`, `records/*.json`, `source/*.diff`, build records, artifacts, `telemetry.jsonl`, `artifacts.json`, `MANIFEST.json` and omission metadata |
| `jiuwenswarm/factory/replay.py`; [TELEMETRY.md](TELEMETRY.md) | Offline read-only capability replay against a disposable store copy, producing `replay:true` events; not agent replay, historical time travel, image inference or a correctness benchmark |
| Run 5 handoff bundle | ****`artifacts/factory/evidence/factory-53db494559954fc6a690a9a014afbf21/` (slim; STORY.txt, PLAN.txt, SLIM-OMISSIONS.json; full export verified 639 files, secrets scan clean)**** prepared path, snapshot time, manifest and omissions after operator preparation; F24 performs no export/replay |

An existing export may lack a session or large artifact bytes; inspect `omissions.json` and any `SLIM-OMISSIONS.json` before assuming completeness. Older runs may have empty/partial telemetry; no retrospective token or call counts are invented. Token fields stay null when unavailable. Telemetry excludes raw prompts/output bodies, and evidence transactions and JSONL emission are not one atomic commit; [TELEMETRY.md](TELEMETRY.md) documents these limits.

The primary Run 5 repair pointers already exist:

| Link | Recorded identity |
| --- | --- |
| Failure | `25ca171cbf99484bbadbbaa5a8698896` (`CONFIG_MISSING`) |
| Revised work | Decision 13; graph revision 13; `factory plan TASK --rev 12` / `--rev 13` |
| Integrated repair | Commit `98d026ef19cfe040cd7da7a4d0692c45253aa1a9` |
| Completed build | `915b94fd95f04f73bc04db2a7503258d` |
| Build receipt | `915b94fd95f04f73bc04db2a7503258d:receipt`; blob SHA256 `b6ee941b3c394cc753c83cd646c2cf8bf04f13e35129a10ae8a76ce641ba1c23` |
| Built image | `sha256:74785dff355483f8185c0e7be0e340c530579dbfb29d3dc595a925e79503f9bb` |

## Controlled-seed disclosure

**The earlier planted `Store.query` slowdown was REMOVED from the baseline.** It is preserved only on branch **`rsi/controlled-seed-store-query`** as a **controlled seed**. Use that branch only with explicit disclosure that the slowdown was planted; any resulting speedup belongs to that controlled experiment and is not a discovered baseline defect. The removal is recorded in baseline history at `a67ca9a0` ("RSI seed removed from baseline").

Do not silently reintroduce the seed, compare a seeded baseline with an unseeded revision as an organic gain, or describe the current baseline as containing it. The opportunities below are genuine headroom, not planted faults.

## Genuine improvement headroom

These are proposed directions, not claims that a fix or accepted speedup exists. Source paths are evidence of current behavior; operator observations and CPU-only work retain their stated limits.

| Opportunity | Current evidence / next discriminating work |
| --- | --- |
| Naive applicability ranking | [expert_streaming.py](../../../jiuwenswarm/factory/expert_streaming.py), `_candidates`: missing quantities and positive cost signals drive a simple score, not causal attribution. Improve ranking using measured bottleneck/evidence value. |
| Evidence requirements do not gate acceptance | `expert_streaming.py:parse_engagement/dispatch` reports `requires_evidence` / `missing_required`; [ab.py](../../../jiuwenswarm/factory/ab.py): `acceptance` uses module obligations without making those generic quantity requirements an acceptance gate. Existing correctness/engagement/module gates still apply. |
| Dispatch check is not atomic with concurrent graph revisions | [api.py](../../../jiuwenswarm/factory/api.py): `dispatch` calls [taskgraph.py](../../../jiuwenswarm/factory/taskgraph.py): `dispatch_precondition` before job submission. Graph-patch CAS does not make this check and submission one transaction; close that race while retaining lifecycle/idempotency. |
| Engagement tool does not read per-token traces | `expert_streaming.py:dispatch` parses stderr artifacts. Integrate actual per-token evidence before making temporal or critical-path claims; summary readiness alone is insufficient. |
| Adaptive read policies absent | Current fill/pregate/inflight settings do not provide adaptive inflight limits, concurrency selection or speculation throttling. Duplicate/unused reads in J-XS2-smoke motivate bounded policy comparisons under comparable cache state. |
| `p12` trace / `p13` populate / `p14` pin / `p15` temporal predictor | Candidates on siminfeng `xs-dev` / `llama-opt` branches are **CPU-tested only**. They are not claimed Jetson image results or part of the eight-component inventory. ****xs-dev/llama-opt branches p12 dba475c0d, p13 c49dfdcde, p14 3d8ad673c, p15 57a881379**** exact branch/commit/patch hashes and CPU evidence paths before integration. |
| F19 placement experiments | `op-offload` prefill-threshold experiments are **pending runs**. Expert placement is separate from streaming; no prefill/decode gain is claimed. ****deferred (open headroom; scripts in xs-dev/placement)**** experiment paths, settings and completed results. |
| `io_bench` full sweep | Not run; device/read-policy headroom is unresolved. ****deferred (open headroom)**** full-sweep plan/result path when separately performed. |

Known tool costs also offer genuine headroom. Approximate timings below are operator-reported observations, not freshly profiled distributions:

| Cost | Evidence / improvement constraint |
| --- | --- |
| `verify_effective_config` ~7.9 s | Real engine/config probe; [inspector.py](../../../jiuwenswarm/factory/inspector.py). Investigate repeated work without substituting requested settings for observed effective settings. |
| Preflight cache miss ~4.1 s | Inspector/preflight path; compare cache misses and hits separately. |
| `evidence.read` hashes the whole blob | [store.py](../../../jiuwenswarm/factory/store.py): `read` / `_verify_blob`, even for a bounded preview. Reduce redundant verification only with preserved artifact integrity. |
| Publish has multiple fsyncs | Store artifact publication and telemetry durability paths; measure call cost while preserving acknowledged durability. |
| Polling consumes turns | [controller.py](../../../jiuwenswarm/factory/controller.py), durable job status calls and turn events; improve waiting/batching using actual lifecycle evidence. |

****siminfeng `c2/RSI-SEED.md` (run-4 call counts and timings)**** attach exact telemetry sequences/attempts, capsule release hashes, host revision and cache conditions for the ~7.9 s / ~4.1 s observations before using them as a scored baseline.

The next segment can choose one opportunity, create a separately versioned capsule/host revision and compare the same workflow with equivalent store contents, inputs, cache/warmup and correctness obligations. Preserve the baseline and negative evidence. Offline `replay` and future export preparation are documented capabilities, not work performed by this handoff.

## Remaining handoff slots

**tag `cc-baseline-2026-11-12` (resolve with `git rev-parse cc-baseline-2026-11-12`)**; **Run 5 stopped by the operator at decision 21 (11/40 turns, 170 min) to cut demo cost; no component kept: mmap_advice and router_prefetch regressed and stay dormant prerequisites; expert_fill was null in two trials (2048 KiB, then a tuning trial at 256 KiB) and was under investigation; cancelled jobs are recorded** terminal decision, source/image/settings and direct comparison; **not run by decision; the improvement claim uses J-OM13 (direct ABBA, plain llama.cpp 841.5 vs factory engine 711.4 ms/token, 12 runs, identical output) and Run 4 records** report and acceptance; **`artifacts/factory/evidence/factory-53db494559954fc6a690a9a014afbf21/` (slim; STORY.txt, PLAN.txt, SLIM-OMISSIONS.json; full export verified 639 files, secrets scan clean)**; **xs-dev/llama-opt branches p12 dba475c0d, p13 c49dfdcde, p14 3d8ad673c, p15 57a881379**; **deferred (open headroom; scripts in xs-dev/placement)**; **deferred (open headroom)**; **siminfeng `c2/RSI-SEED.md` (run-4 call counts and timings)**. Presentation captures/cues are tracked in [DEMO-10MIN.md](DEMO-10MIN.md). None of these slots implies the work has completed.
