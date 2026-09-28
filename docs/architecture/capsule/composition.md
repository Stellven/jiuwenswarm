# Composition

**Unchecked at M1. Unlocks: composer.** The schema has the fields now, so nothing built for M1 gets in the way. M1 neither requires nor tests them.

**Composition.** When a group of capsules often runs together and passes, it can become one new capsule of kind `composite`. The simplest case is A then B becoming A-B. The composite pins its members by `decl_hash` and runs them unchanged. A, B and A-B all stay in the library, and any of them can be chosen. Capsules are never split; larger capsules are only built from smaller ones.

**Fusion** is a proposal, not decided: the code inside A-B would be rewritten to do the work in one pass, and compared with A-B on stored inputs.

## Schema

On the Declaration, all unchecked:

- `members`: each `{id, decl_hash}`. It is set instead of `carrier`, `body` or `remote`. `id` is the member's local name.
- `structure`: `sequence`, `parallel` or `graph`. Required with `members`.
- `wiring`: each `{from, to}`. `from` is `inputs.<port>` or `<member>.outputs.<port>`; `to` is `<member>.inputs.<port>` or `outputs.<port>`. With `graph`, it gives the order.
- `code_sha256`: the hash of the `members` list sorted by `id`. Each member's own `code_sha256` pins its code.
- Lineage: `identity.lineage.relation: merges`, `parent` is one member's `decl_hash`, and `co_parents` lists the others. `co_parents` is required when `relation` is `merges`.

The `composite` value of the `capsule_kind` registry is unchecked in the policy.

## Rules

- **Only admitted capsules are composed.** Two capsules that each pass are not assumed to pass together: the composite earns its own Verdict.
- **Tests:** the union of the members' test suites, plus the composite's own.
- **Proposals:** a composer proposes a composite from Observations of capsules that run in sequence and pass. Every composite proposal is approved before it is built. A gate is never inside a composite.
- **Costs.** A-B declares all of its members' effects. A retry repeats the whole of A-B, and a failure is recorded against A-B.
- **When a member changes.** If A gets a new version A′, A-B keeps pinning A; it picks up A′ only in a new composite version. If a member is revoked, the librarian moves A-B's Standing to `suspect`.
