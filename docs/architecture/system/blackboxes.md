---
type: design
status: draft
version: 2
owner: muk
sources: [../PROCESS.md, ../open-issues.md, ../decisions.md]
provides: [system.blackboxes]
consumes: []
depends_on: [overview.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
tags: [system, blackbox]
---

# Black boxes: only unresolved product or safety boundaries

The full M1 PRD is available. Architecture uses sourced, replaceable defaults for missing implementation detail and records them in the [decision ledger](../decisions.md). `blackbox` is reserved for a product conflict or safety boundary that cannot honestly be marked implementable.

## Active black boxes

| Boundary | Published provisional interface | Blocking condition | Unblocked when |
|---|---|---|---|
| macOS generated POC execution | [`PocExecutionRequest/Result`](../capsule/process-boundary.md) and the common ExecutionProfile | no verified macOS equivalent for path/network/credential/fixture isolation | an execution profile passes every negative probe; until then it returns `UNSUPPORTED_SECURITY_PROFILE` |
| Hidden RSI fixture oracle deployment | [`FixtureEvaluationRequest/Result`](../capsule/fixture-oracle.md) | root-free wording conflicts with the administrator-provisioned Linux principal model; enforcement is unvalidated | product resolves bootstrap and the runner/oracle principal and IPC probes pass |

These conditions block only generated or hidden execution on the affected platform. They do not block schema, parser, store, Gate, CLI, ordinary capsule, or Linux implementation work.

## Drafts that are no longer black boxes

Screening decisions 48–53, threshold semantics, execution roles, offline wheelhouse, scientific classification, Gate profiles, RSI query scheduling and trusted-method registration have provisional or adopted dispositions in [decisions](../decisions.md). Their pages remain `draft` until lint, canaries and review pass. Missing method coverage blocks the selected experiment; it does not make the protocol a black box.

## Promotion and recheck

Resolve a blocking condition through its owning schema/profile version. Recheck all producers, consumers, Gate/profile bindings, seams, run plan, records, coverage and diagrams. Passing lint is structural evidence, not platform validation.
