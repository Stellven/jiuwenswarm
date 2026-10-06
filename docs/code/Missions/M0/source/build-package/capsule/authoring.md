# Authoring and publishing a capability capsule

## Lifecycle

1. **Declare.** State purpose, kind, typed ports, preconditions, dependencies, effects, guarantees, checks, and applicable limits. Keep objectives, node IDs, permissions, verifier assignment, and run policy outside.
2. **Choose form.** A leaf points to implementation by locator and hash. A composite pins members and describes its internal graph and wiring. Do not promise unsupported fusion.
3. **Build.** Keep code separate and pin covered files. Preserve the declaration's meaning. A node objective binds one or more admitted CCs under a separate Node Execution Contract; subordinate calls keep their own identity, authority and evidence. A CC assesses; the gate decides and releases.
4. **Verify.** Run applicable tests and characterization checks; retain outputs, check results, and evidence references against the exact declaration and implementation hashes. A passing self-test alone is not admission.
5. **Admit.** A trusted path checks declaration, hashes, dependencies, and effects. M1 runs deterministic checks before an independent verifier reviews the evidence. The gate host records the decision; unsupported obligations block admission or binding. Spec Kit owns detailed policy.
6. **Publish.** Store an immutable version with references, hashes, and admission record. New versions do not change existing runs.
7. **Activate.** A human-controlled pointer selects admitted versions for future plans. RSI candidates remain inactive until admission and human activation. Reversion changes the pointer, not prior records.

## Authoring rules

Prefer wrapping a working JiuwenSwarm/OpenJiuwen capability. Keep the summary task-independent. Declare effects and repeat safety; prose grants no permission. Type and check outputs. A composite pins members by hash and exposes only a boundary it can guarantee.

The companion description and schema disagree on requiredness, shapes, and enums. Use [the declaration inventory](declaration.md); Spec Kit must reconcile and version the format before implementation. Do not invent keys.

Protected configuration or the frozen graph assigns runtime criteria. Keep verifiers, gates, check runners, hidden fixtures, and their behavioral dependency closure outside RSI mutation. Declared checks do not grant release authority.

## Change rules

Preserve each version's meaning. Changes to ports, guarantees, effects, or compatibility require a new version and admission. Record lineage where supported. Library changes apply to future freezes; active runs keep pinned versions and checks.
