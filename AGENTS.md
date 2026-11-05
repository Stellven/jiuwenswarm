# AGENTS.md — branch `ai4r_ccv2`

## Branch purpose (read first)
This branch is a deliberate scope reset. It is base JiuwenSwarm plus the preserved Codex integration plus a new Capability Capsule (CC) v2 runner exposed to agents as native tools.

The M1 research machinery was removed on purpose: the Intention/intent Compiler, the old capsule pipeline and `capsule_runtime`, `jiuwenswarm/research*`, the RSI console, ccbench/harbor benchmarks and `deploy/m1`. **Do not restore, extend or re-create them, and do not follow the M1 PRD / TASKS / Spec Kit process that earlier versions of this file described.** The old file is kept on `AI4Research-Main` and in git history.

Start here instead:
- `docs/architecture/README.md` — what the branch is and how the pieces fit
- `docs/architecture/ccv2/README.md` — install, start, demo
- `docs/architecture/ccv2/PROVENANCE.md` — base and source revisions
- `docs/architecture/ccv2/PROTOCOL-CHANGES.md` — changes made to the CC protocol, with evidence
- `jiuwenswarm/ccv2/` — the runner; `demo/ccs/` — demonstration CCs

## Working rules
1. Build real things; no reports, audits or tests that were not asked for. Fix the pipeline in general; never hard-code a result to make a check pass.
2. Do not label a simulation as a live-agent or image result. Tests are distinct from live runs.
3. Keep the protocol lightweight: no registry service, planner or intent compiler.
4. Preserve unrelated work and credentials; never write secrets into artifacts. Do not commit, push, merge or deploy unless asked.
5. 5175 is the only local web host port.
6. Codex integration lives in `jiuwenswarm/server/runtime/codex_subscription/`, `agent_adapter/interface_codex.py`, `gateway_adapter/codex_adapter.py` and `jiuwenswarm/codex_start.py`. Keep them free of imports from removed packages.
