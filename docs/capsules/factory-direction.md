# Capability capsule factory: fixed control, adaptive work

**Recommendation: use both.** Make the outer production lifecycle a fixed,
durable pipeline. Put adaptive agents inside bounded stages for understanding
repositories, resolving dependencies, implementing candidates and responding to
public development failures. The agent may choose how to build; it cannot change
the release rules or certify its own result.

| Approach | Useful property | Main weakness |
| --- | --- | --- |
| One adaptive agent owns everything | Handles heterogeneous repositories and unexpected work | Hard to reproduce, resume, bound and separate author from judge |
| Fully fixed production recipe | Clear stages and repeatable operations | Brittle across repository layouts, build systems and capability gaps |
| Fixed lifecycle with bounded adaptive stages | Flexible implementation with durable evidence and protected release | Requires explicit stage contracts, budget accounting and checker ownership |

The capsule work exposes a useful initial factory contract: produce an immutable
**candidate package**, not an active capability. Keep source acquisition,
authoring, checking, qualification, admission and activation distinct. Current
M1 manually exercises these boundaries; this document proposes future automation.

## Proposed lifecycle

1. Intake a capability gap or repository request with original run evidence,
   purpose, rights/licensing constraints and hard limits. Generalist outputs are
   low-trust hints, not verified requirements or automatic triggers to build.
2. Resolve an immutable source revision and dependency lock. Reuse an existing
   specialist when suitable; declining to build is a valid outcome.
3. Freeze an achievable declaration, typed ports, effects, budgets, explicit
   unsupported behavior and independently owned checking strategy.
4. Give an authoring agent a disposable workspace with scoped tools and a finite
   budget. It may inspect public development feedback and revise its candidate.
   Each iteration creates a new candidate identity and retains prior evidence.
5. Run mechanical packaging, isolation, dependency, schema and function checks.
   Then run independently assigned semantic/behavior checks against the frozen
   promises. Private held-out cases remain behind the evaluation boundary.
6. Produce a qualification report with actual observations and limitations.
   Missing infrastructure/authentication is blocked, not PASS; a failed or
   indeterminate required check cannot advance. Broadening a failed declaration
   or weakening checks requires a new reviewed contract, not agent discretion.
7. Submit the package through normal admission and human M1 activation. Future
   automation may apply an explicitly approved policy, but source merge, a
   successful experiment and Generalist success never imply promotion.
8. Publish exact eligible versions for **future** frozen plans and monitor their
   outcomes. Retain rollback pins and revoke/retire versions through explicit
   Library operations. Do not inject a new capsule into a running DAG.

The outer controller owns durable stage identity, leases, idempotent retries,
cancellation/containment, checkpoints, budgets and evidence. Agents get typed
stage inputs/outputs and finite tool grants. Retry a safe transfer or build
step by its content identity; reconcile unknown external effects before retry.
No implicit recursive factory calls or unbounded improvement loops.

## How this fits RSI, labs and containers

The factory acquires a missing capability or creates a new package. RSI improves
an existing declared capability under a bounded scope and lineage. They may
share builders, evaluators and packaging, but neither is the admission authority.
A durable lab can keep project state, change models and propose useful versions
back to the shared AI4R base. Its local success remains candidate evidence until
the central process independently accepts it.

For M2 container capsules, retain the same lifecycle and add a pinned image
digest, architecture, runtime protocol, dependency/SBOM and confined resource
profile to the package. A Python package passing M1 tests does not prove that
image isolation or ARM64 execution works. Keep the protected verifier and
admission authority outside the candidate's container and writable workspace.

Build on development machines/CI where practical, stage selected immutable
images and inputs to Spark, run benchmarks there, inspect, and retrieve verified
results. Share immutable dependency layers and a central model service/weight
store; do not bake model weights into every capsule image or copy them per lab.
Account for image layers, model weights, repository clones, scratch and retained
evidence separately. Apply the repository-owned seven-day expiry only to owned,
inactive temporary resources; protect results, inputs, models, credentials and
rollback pins, and retain 20% filesystem growth headroom. This is consistent with
the separate deployment workflow and does not make Spark a development or
factory prerequisite.

## Next practical increment

Automate candidate packaging and public development evaluation first, using the
repository module convention and release manifests. Add durable factory jobs
and bounded adaptive authoring only after that contract is stable. Keep manual
admission/activation until there is measured evidence and explicit approval for
a promotion policy. Benchmark whether generated specialists improve declared
behavior over Generalist; do not optimize only for task completion or capsule
count. The current changes implement none of this factory automation.
