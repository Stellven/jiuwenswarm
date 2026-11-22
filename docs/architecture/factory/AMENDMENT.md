# Feature-scoped amendment: iterative inference-engine software factory using CCs

Status: authorized by the operator on 2026-11-12. On M2 it applies to the factory feature only; the M1 research runtime keeps its own rules.

## What changes
`AGENTS.md` rule 3 and `docs/architecture/README.md` forbid a planner. For the **inference software factory feature only**, the operator authorizes an *iterative, evidence-driven controller*:

- One real JiuwenSwarm agent (Codex subscription SDK) is the decision maker. It repeatedly queries the factory evidence store, records a versioned **decision** (observations, hypothesis, uncertainty, next bounded action, expected evidence, budget, stop condition), invokes Capability Capsules, ingests results, and decides again.
- A plan is a revisable working decision with evidence references. It is **not** a frozen graph and not the M1 intent compiler.
- The host (`jiuwenswarm/factory/`) enforces authority, durable state, identity and job lifecycle. It does not choose actions.

## What does not change
- The factory does not import or drive the M1 intent compiler, capsule pipeline (`capsule_runtime`), `jiuwenswarm/research*`, the RSI console, ccbench/harbor or `deploy/m1`. Those remain M1's and are unchanged.
- Grants come only from the operator (`--grant`, `--workspace`, factory task `allowed_effects`). Replanning never widens authority and never changes a scored evaluation contract; a changed contract is a new revision with a new comparable run set.
- CC protocol, schemas, receipts, key replay and the eight agent tools are unchanged. Native CCs remain `trusted_local`, not an isolation boundary.
- Provenance, credential and port rules are unchanged.

## Scope boundary
The amendment covers `jiuwenswarm/factory/`, its capsules under `jiuwenswarm/factory/ccs/`, the `jiuwenswarm-factory` CLI, the Factory runs web routes and page and the docs under `docs/architecture/factory/`. Everything else follows `AGENTS.md` as written.
