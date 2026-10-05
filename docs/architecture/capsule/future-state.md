---
id: capsule.future-state
type: capsule
level: detail
status: proposed
provides: [capsule.future_state]
depends_on: [capsule.md, fields.md, library.md]
tags: [capsule, future-state]
prd: [4.1.3, 4.1.4]
---

# Future state: composition, generalist, Symphony

PRD: 4.1.3, 4.1.4

> Answers: What is deliberately left out of M1 capsules (composition, generalist, Symphony)?

Nothing here is built, required or tested at M1. M1 [runs](../system/lifecycle.md#term-run) the fixed outer flow and a fixed-template planner (no model call) over admitted `tool` and `skill` [capsules](capsule.md#term-capability-capsule) ([flow](../flow.md), [capabilities](../capabilities/README.md)). The page exists so schema fields reserved for these ideas keep a stated meaning. Disabled fields are rejected as `M1_FEATURE_DISABLED` ([stages](stages.md), [fields](fields.md)).

## Composition

Deferred. A capsule is a graph of capsules: a singleton is one node with its own code; a composite lists `members` (each pinned by `decl_hash`) and `wiring`, never both code and members. The fields `members`, `wiring`, `identity.lineage.co_parent_hashes`, `changes.provides[]` and `needs.injects[]` are reserved and unchecked.

- A pair "A then B" that recurs and passes could be proposed as a composite A-B, tested as one block (union of the members' suites plus its own), approved by a person, and later fused into one code item with the same [interface_hash](fields.md#term-interface-hash). A, B, A-B and the fused form all stay in the library.
- Pinned members never move: a new A makes A-B stale, and a `suspect` or `revoked` member makes A-B `suspect`.
- [Gates](../verification.md#term-gate) stay outside composites and are chosen by the workflow, never by a capsule.
- Mid-run install and uninstall (spatiotemporal composability) are deferred further: between runs, a new or removed capsule takes effect from the next run, which keeps the versions it pinned.
- Why deferred: no M1 block needs it and the PRD whitelist excludes composites. Open: nesting depth, cycles, a `relation` value for fusion.

## Generalist

Deferred. A permanent low-trust capsule of [kind](capsule.md#term-capsule-kind) `agent_template` (one per harness, each pinned by `identity.remote`) that would fill a step no admitted capsule fits, leave a gap Finding with its trajectory, and never write the library. It would be level `exempt`, bound only on [steps](../system/nodes.md#term-step) whose outputs have deterministic or reference [checks](fields.md#term-check), never where a certified capsule is required. Generalist gap repair is outside the M1 whitelist ([RSI](rsi.md)); a failed step in M1 [halts](../system/lifecycle.md#term-halt) the run.

## Symphony and CC

Deferred. Symphony (agent-core) indexes installed capabilities and plans which to use; it runs and checks nothing. A later CC provider would expose admitted capsules only, with declared [ports](fields.md#term-port) as capability I/O, and CC would freeze the planned graph into [Bindings](../schemas/binding.md#term-binding). M1 emits a fixed template with its own planner and [validator](../system/planner.md#term-plan-validator) ([planner](../system/planner.md)); Symphony is not a dependency. Open: whether tool capsules can be graphed there, and a deterministic `plan()` path.

## Other deferred items

Certified trust and per-promise assurance ([trust](trust.md)), importing outside tools or MCP servers, remote `mcp` and `a2a` capsules, automatic librarian drift and policy changes, dynamic capsule selection and ranking, budgets on tokens or money, and capsule interaction analysis ([library](library.md)). Each is a field value or unchecked column in [stages](stages.md); none is an M1 requirement.
