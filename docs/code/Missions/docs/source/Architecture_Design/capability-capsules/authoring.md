# Authoring and publishing a capability capsule

`Tier 2 · Part of: [2. Capability Capsules](../2-capability-capsules.md)`

Question answered: What must a CC author provide and which decisions belong to infrastructure?

## Lifecycle

Field-level rules for the declaration are in the [declaration reference](../reference/declaration.md) and its [schema](../reference/schemas/capsule-declaration.schema.json). This page keeps only the lifecycle and who decides what.

1. **Declare and build.** The author declares purpose, ports, effects, guarantees and limits, keeps objectives, node IDs, permissions, verifier assignment and run policy outside, and pins the covered files. The author never writes mandatory checks or gates ([D42](../method/decisions.md#d42)). A CC assesses or produces. The gate decides and releases.
2. **Self-test.** The author runs tests against the exact declaration and implementation hashes. A passing self-test is neither admission nor approval of mandatory checks.
3. **Mandatory checks.** An independent check maintainer authors and versions the deterministic bundle, records the CC versions it supports and supplies compatibility evidence. The author cannot approve or alter it. Protected binding adds run-specific contract and policy checks separately.
4. **Admit.** M1 starts from the designated bootstrap set with exact CC and bundle identities recorded. New or changed versions need protected admission that reviews identity, dependency closure, permissions, independent evidence and the compatible bundle. Under D21 the M2 path may automatically admit a passing RSI version only when a pre-approved association uniquely covers it. Unsupported required checks block admission or binding.
5. **Publish and select.** Immutable CC and bundle versions, their association and the admission record are stored. M1 activation is a human act. Existing runs keep their exact pins. Reversion changes future selection only.

A change to implementation, ports, guarantees, effects or check compatibility needs a new immutable version and the applicable admission. A bundle change makes a new bundle version and association. It never updates a CC version or an active run. Record lineage where supported.

The author decides what RSI may change through `evolution.rsi` and `evolution.may_change` ([D34](../method/decisions.md#d34), [rules](../reference/declaration.md#evolution-what-rsi-may-change)). Verifier CCs and CCs whose output is gate evidence are `none`. Per-CC pages: [capsule build references](../reference/capsules/README.md).
