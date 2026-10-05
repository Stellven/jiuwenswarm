---
type: review
status: checked
version: 1
owner: muk
sources: [../model-routing/README.md]
tags: [review, model-routing]
---

# Review: model routing reply, 2026-10-01

One adversarial review (Opus) of [the reply](../model-routing/README.md) v3. Each finding was checked in source before it was applied.

| # | Finding | Severity | Applied |
|---|---|---|---|
| 1 | A router's own failure became the caller's `CAPSULE_ERROR`, not a runtime reason | blocker | A router failure never fails the work: the capsule falls back to its default model. Endpoint failures stay runtime-owned |
| 2 | Skills and gate capsules cannot route: the handler reads only `SKILL.md`'s `model` | blocker | At M1, routing is for `tool` capsules; skills route later through the handler |
| 3 | No defined replay of a router's decisions; a router's model turns shift `model_replies` | major | The router runs under `cc.replaying()` with fixture catalogs; `model_replies` are one order across the call tree ([runner](../capsule/runner.md#the-model-client-contract-m05)) |
| 4 | A router writing its own audit store breaks M1 permissions and `effects_cover_dependencies` | major | A decision is the router's output Artifact; the audit tables are a view ([ledgers](../system/ledgers.md)) |
| 5 | seams.md and runner.md still placed a router behind M05 | major | Fixed: M05's `route_record_id` is only for an endpoint that routes itself |
| 6 | A `route_id` never passed to `cc.model` joined to nothing | major | Fixed by 4: `produced_by` and `causation_id` join every decision. `cc.model.turn` now carries the hint and route |
| 7 | A router's pin fixes its code, not its routes, once the catalog changes | major | The router declares `reads_external`; each decision names its catalog version |
| 8 | Verdicts and Standing say nothing about which model ran | major | The reply says what a Verdict certifies, and that quality is measured per model before Standing or RSI acts |
| 9 | Freeze still calls a revoked pinned dependency | minor | [Open issue](../open-issues.md) 39 |
| 10 | The broker's R7 interface dropped `route_id` | minor | Fixed |
| 11 | Router ports deferred past M1 | minor | Ask 2: propose them before M1 ends |
| 12 | Redundant points | minor | Page shortened to six rules |
