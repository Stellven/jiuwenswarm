---
id: arch.k8s_lens
type: design
level: present
status: draft
version: 1
provides: [arch.k8s_lens]
consumes: [arch.terms]
depends_on: [terms.md, flow.md, runtime.md, isolation.md, system/lifecycle.md, capsule/admission.md, capsule/fields.md]
tags: [design-patterns, kubernetes, start-here]
prd: []
prd_note: Design aid; borrows Kubernetes patterns and implements no PRD clause
---

# Kubernetes as inspiration

> Answers: Which Kubernetes patterns do we borrow, and where?

We borrow patterns from Kubernetes (k8s) where they fit. We do not run k8s, use its API, or claim equivalence. Each row says which pattern, where we use it, and why. If a pattern does not fit, the row says so.

## Pattern map

| k8s idea | Our version | Why it helps | Where |
|---|---|---|---|
| **Spec vs status.** Desired state is written once, observed state is reported separately | **[Declaration](capsule/fields.md#term-declaration)** and **[run plan](types/run-plan.md#term-run-plan)** are spec. **[Observation](schemas/observation.md#term-observation)**, **[Verification](schemas/verification-record.md#term-verification)** and the release record are status. Status never edits spec | a run can be explained and replayed from records | [terms](terms.md), [lifecycle](system/lifecycle.md) |
| **Controller reconcile loop.** Read actual state, compare to desired, take the next step | The **supervisor** restarts from committed records and takes the next action (run dispatch, [Gate](verification.md#term-gate) release, halt). It never trusts memory or caches | crash recovery without special cases | [lifecycle](system/lifecycle.md) |
| <a id="term-api-server-is-the-only-writer-to-etcd"></a>**API server is the only writer to etcd** | The supervisor is the only writer to the store. Everything else sends requests | one place to keep records consistent | [placement](placement.md), [storage](system/storage.md) |
| <a id="term-immutable-images-pinned-by-digest-tags-are-movable"></a>**Immutable images pinned by digest, tags are movable** | Capsule versions are pinned by hash. The active alias is a movable pointer. Activation moves the alias, never a version | rollback is moving a pointer. Frozen runs never change | [library](capsule/library.md) |
| **Pod spec** (image, env, limits, [ports](capsule/fields.md#term-port)) | **[Binding](schemas/binding.md#term-binding)**: [capsule](capsule/capsule.md#term-capability-capsule) version, typed inputs, limits, Gate | one record says exactly what ran | [runner](capsule/runner.md) |
| <a id="term-pod-one-run-of-a-container-restartpolicy-never"></a>**Pod = one run of a container, restartPolicy: Never** | A **node** is one run of a CC. **Zero autonomous retries**. A new attempt is explicit and human-started | failed runs stay clean evidence | [runtime](runtime.md) |
| <a id="term-job-with-backofflimit-0"></a>**Job with backoffLimit 0** | A run: it succeeds, or halts and keeps evidence | no silent repair loops | [runtime](runtime.md) |
| **Admission controllers** (validating, mutating) | **Admission**: mandatory [checks](capsule/fields.md#term-check) first, then a policy-selected provider. [Puppet admission](capsule/admission.md#term-puppet-admission) is a developer allowlist | nothing enters the library unchecked | [admission](capsule/admission.md) |
| <a id="term-crds-with-openapi-schemas-versioned-apiversion"></a>**CRDs with OpenAPI schemas, versioned `apiVersion`** | Types and messages have JSON Schemas with a `version`. Core types are closed. A change is a new version plus an adapter | code is generated from schemas | [contracts](contracts/README.md), [types](types/types.md) |
| <a id="term-dry-run-server-side-validation-before-apply"></a>**Dry run / server-side validation before apply** | The plan **validator** checks a proposed DAG before anything is dispatched | a bad plan never runs | [planner](system/planner.md) |
| <a id="term-scheduler-filter-then-score"></a>**Scheduler: filter, then score** | Planner/validator **filter** (types, versions, permissions, budgets). Model routing **scores** inside one call and never picks capsules | clear separation of what must hold and what is preferred | [placement](placement.md) |
| **securityContext, PodSecurity "restricted"** (non-root, drop capabilities, read-only root, [Landlock](isolation.md#term-landlock), no privilege escalation) | **Restricted children** use named execution profiles: separate non-root identity, dropped capabilities, no new privileges, [seccomp](isolation.md#term-seccomp), read-only code | the least needed, set per profile | [isolation](isolation.md), [process boundary](capsule/process-boundary.md) |
| <a id="term-networkpolicy-default-deny"></a>**NetworkPolicy default deny** | Children have no network. Only brokers talk out | no ambient access | [isolation](isolation.md) |
| <a id="term-secrets-mounted-only-where-needed"></a>**Secrets mounted only where needed** | Credentials live on a volume only the model bridge mounts | login unreachable from capsule code | [placement](placement.md) |
| <a id="term-sidecar-ambassador-pattern"></a>**Sidecar / ambassador pattern** | The **model bridge** is an ambassador: capsules talk to a local broker, the bridge talks to Codex | auth and capture in one place | [placement](placement.md) |
| **Resource limits** (`limits`, LimitRange) | Per-call budgets: time, memory, processes, output size. First limit hit kills the child tree | bounded cost and runaway control | [runtime](runtime.md) |
| <a id="term-liveness-and-readiness-probes-init-containers"></a>**Liveness and readiness probes, init containers** | **Doctor** probes and `/ready`. Bootstrap steps run before the service accepts work. A failed probe blocks that workload | unsupported setups fail early | [deployment](system/deployment.md) |
| **Events** are informational, not authority | `cc.*` events are views. Records are authority | UI cannot change what happened | [observability](system/observability.md) |
| <a id="term-labels-and-ownerreferences"></a>**Labels and ownerReferences** | `obs_id` joins everything in one call. Lineage fields link versions. Attempt directories belong to their attempt and are removed only after capture is sealed (proposed) | traceability and clean-up | [observability](system/observability.md) |
| **Lease** (leader election) | One run lock per run. A second launcher refuses | no double dispatch | [lifecycle](system/lifecycle.md) |
| <a id="term-generation-observedgeneration-idempotent-apply"></a>**Generation / observedGeneration, idempotent apply** | `dispatch_id` and `attempt`. Same request id and bytes return the same result. Changed bytes conflict | safe duplicates and resume | [lifecycle](system/lifecycle.md) |

## Where we differ on purpose

- **No self-healing.** k8s restarts failed pods. We halt and keep evidence, because a research run must be reproducible and an automatic retry could repeat a paid model call or an effect.
- **No eventual consistency.** A node is [released](system/lifecycle.md#term-release) only after a committed pass. k8s controllers converge over time.
- **One run at a time, one host.** No cluster, scheduler fleet or multi-tenancy in M1.
- **No RBAC objects.** Local single user. Permissions come from Declarations and execution profiles.

## What this lens gave the design

1. Name the profiles (`restricted-child`, `poc`, `oracle`, `bridge`) like PodSecurity levels, and keep each as one reviewable record.
2. Treat the planner output as a proposal that passes validation, like an object passing admission.
3. Keep spec immutable. Any change to spec is a new object (new version, new run).
4. Recover by reading state, not by remembering.
