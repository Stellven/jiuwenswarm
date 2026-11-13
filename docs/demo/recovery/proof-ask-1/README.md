# Proof run: tell a JiuwenSwarm agent the CC task directly (no web frontend)

13 Nov 2026, 13:32–13:46 UTC, on Satay. Task `factory-cc5e8585445c484ba4d5b5b0dd96c31c`. Outcome: **accept**, 3 turns, 13 min 10 s.

## How it was invoked

```sh
cd ~/projects/jiuwenswarm
.venv/bin/jiuwenswarm-factory ask "<instruction below>" --model gpt-6.1-sol --branch proof-ask-1
```

**Instruction:**

> Use engine.expert_streaming to apply demand fill to plain llama.cpp cf34d3113 on your owned branch. Integrate expert_fill together with its declared source prerequisites (mmap_advice, router_prefetch) with their runtime switches off, committing each component. Build the candidate exactly once with factory.builder. Then run exactly one screen lab run (lab_client) of that image under the frozen contract qwen36-quick-v1 with the expert_fill component environment, to check output identity against the frozen reference and that fill engages. Then finish with a report of the commits, image, screen result and engagement. Do not run ABBA comparisons, do not integrate other components, do not tune settings.

**Path the instruction takes:**
1. CLI (`jiuwenswarm/factory/cli.py ask`)
2. factory controller
3. JiuwenSwarm agent adapter
4. Codex app-server over stdio (pinned 0.163.0, model `gpt-6.1-sol`)
5. the CC runner (`jiuwenswarm.ccv2.agent_mcp`, an MCP server), exposing the factory capsules
6. builder and lab jobs on the shared host queue

No web frontend or server is involved.

## What happened (all from the factory store; see STORY.txt and PLAN.txt)

| Step | Evidence |
|---|---|
| Capsules read; applicability passes (read-only) | rev 1 |
| Three capsule components integrated as separate commits on the owned branch `proof-ask-1`: `133bdac08` mmap_advice, `679bd0e1e` router_prefetch, `885eec824` expert_fill | rev 2. All five declared patch sha256 values and forward checks verified. Tree `d63f6127…` is **identical** to the fill candidate of the 13 Nov recording, so the integration is reproducible. |
| Built once via `factory.builder` | build `3445e556`: 165 s, CUDA 12.6 sm_87 release → image `factory/llamacpp:proof-ask-1-expert-fill` `sha256:a15f04f0…`, admitted for jetson-orin |
| One screen via `factory.lab_client`, frozen contract `qwen36-quick-v1` | lab `bbc85611`: **stdout `cad62aa9…` equals the frozen reference**; correctness pass, evidence complete |
| Fill engaged | Fill active (threads=16, chunk_kib=2048, random=decode), decode random advice applied, 1240 fill calls, 6.59 GB read during decode, 566 ms/token demand wait |
| Decision | rev 5 `accept`: frozen correctness plus demand-fill engagement, as instructed |

**Work graph.** All 10 work nodes carry `engine_slice: expert_weight_readiness` and `contract:qwen36-quick-v1`. This is the first live task to use the ontology link added in `6d10c8c5`.

## Limits

- **Not a speed claim.** The screen's 898.36 ms/token is a single preliminary run, and no comparison was run.
- **Contract-level engagement 0/2.** These two checks are for the effective-config line and the fill thread names. The fill-only source has no patches 08/09, so they are not measured. Fill engagement was established by the component's own checks.
- **Operator-directed scope.** The instruction fixed the scope (which components, one build, one screen). The agent chose the commit order from the declared dependencies, verified the patches, and chose to accept on the evidence.

## Where the evidence is

- **Sanitized export:** `~/backup/proof-ask-1-evidence/` (14 MB). Credential pattern scan: no hits.
- **Task JSON:** `task.json`, generated from `jiuwenswarm/factory/tasks/direct.json`.
