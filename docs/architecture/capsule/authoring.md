# Authoring a capability capsule

## Intent

Make the smallest reusable capability that explains what it does and what callers can trust. Prefer wrapping working JiuwenSwarm/OpenJiuwen code to rebuilding it.

## Authoring route

1. State the capability's purpose without tying it to one node or run. If it performs unrelated jobs, separate them.
2. Choose a tool or model/skill-backed execution form. Reference the existing implementation or the smallest new wrapper.
3. Describe named inputs and outputs using the [declaration format](declaration.md). Reuse an existing compatible data contract; let the owning task define a missing one.
4. Explain dependencies, requested access, and effects. Keep access scoped to the capability's job, particularly for generated code.
5. State useful guarantees and relevant checking hooks. Explain important failure behavior without copying the runner's standard error catalog.
6. Use Spec Kit to implement and verify the capsule and its connected boundaries. Publish its declaration and implementation together as a versioned capability.

Keep the declaration independent of provider, concrete request, UI, and test suite.

## Calling a capsule

The planner may use many nodes for a task. Each binds one CC and its inputs. The runner supplies context and records internal calls; orchestration applies assigned checks.

Internals may change while preserving the authored interface. Changes to input meaning, guarantees, or effects need a compatible extension or new version. For example, executing experiments instead of only writing code changes the effects callers must expect.

## Verifier capsules

A verifier author describes what question it can check, which evidence it needs, and what result it returns. Reuse deterministic tooling for mechanical questions. Use semantic or scientific review where it adds information.

The verifier does not choose whether its own result is sufficient to release a node. Fixed-stage configuration or the frozen plan assigns that role; the gate mechanism applies the decision. Keep verification criteria separate from the producing agent's editable workspace.

## Implementation freedom

Authors choose algorithms, internal helpers, prompt details, and private data formats through their coding tasks. They must preserve the declaration's meaning and run boundaries. Propose a change when the contract prevents a substantially simpler implementation; do not silently weaken it.
