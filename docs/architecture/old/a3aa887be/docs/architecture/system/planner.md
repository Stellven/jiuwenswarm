---
type: design
status: draft
version: 2
owner: muk
sources: [../m1/control-flow.md, integration.md]
provides: [system.experimental_planner, system.plan_validation]
consumes: [m1.control_flow, cc.type.run_plan]
depends_on: [../m1/control-flow.md, ../types/run-plan.md, ../capsule/library.md, lifecycle.md]
tags: [system, planner, m1]
---

# Planner, validation and binding

## Position in the fixed flow

SwarmFlow runs required intake, intent/Gate, requirements/Gate, planning, validation/binding/freeze, dispatch and delivery positions. The planner operates **after accepted requirements**, before task-DAG execution. It is an ordinary orchestration service, not a capsule. The requirements determine task nodes and data connections; validation and freeze make that DAG fixed before dispatch. This replaces the old experimental-only planner and fixed-template production bootstrap.

## Responsibility and inputs

- Inputs: accepted immutable requirement contract with source/intent references, admitted library snapshot, effective policy/configuration and request/run identity.
- Output: a captured candidate plan containing capability selections, node dependencies, typed input/output bindings, required Gate profiles, resource budgets and objective-to-terminal-output coverage.
- The planner chooses work structure, not credentials, filesystem permissions, referee policy or active aliases. No generated source code is executable dispatch authority.
- Default model: GPT-6.1 Sol through the protected Codex adapter. Existing placement stays `cc/planning/service.py`, pure validator `cc/planning/validate.py`, native Leader adapter `cc/adapters/leader.py`. [Reuse audit](reuse-audit-2026-10-05.md) records the actual pinned native symbols; their native approval is not CC authorization.

## Validation, binding and freeze

1. Commit a planning reservation and capture the request under an authenticated bounded model scope. Failed persistence prevents model work or dispatch; duplicate identities reuse reserved state rather than issuing another paid call.
2. Preserve the captured proposal as an immutable Artifact. A model proposal is not permission to execute.
3. Check exact type versions or pinned adapters, available required inputs, unique nodes, acyclicity, dependency closure, admitted versions, reachability, objective coverage, permissions, budgets and required Gates.
4. Bind every planned work node to an exact admitted work capsule and its Gate profile/verifier. Pin the accepted task, source resources, library/configuration/policy closure and complete Binding set. Check current revocation without silently substituting aliases.
5. Dispatch only from committed valid/frozen state. Inject accepted task data and resource references into declared DAG ports. SwarmFlow processes dependency-ready nodes; no parallelism guarantee is introduced.
6. Each work call persists output/capture and enters its Gate boundary. Only committed advancing Verification and release unlock consumers. Failed Gates halt all further work dispatch for the run, including sibling branches. Delivery processes accepted terminal results as ordinary code.

## Authority and failure

One shared `research.verifier` identity supplies semantic assessment through pinned profiles; every Gate-role capsule has zero RSI-mutable components. The Gate host folds deterministic checks and assessment; supervisor/store custody remains the durable authority. The planner cannot release work, repair an executing graph, retry uncertain model calls silently or activate candidates. Explicit recovery reconciles committed state; changed task/policy/implementation pins require a new run.

SkillFuzz interaction analysis is deferred. Structural validity does not prove semantic success of a capsule combination. Bounded plan fixtures cover wrong versions, missing producers, cycles, unreachable objectives, denied effects, missing Gates, budget overrun, timeout and failed validation writes; invalid plans cause zero dispatches.

## Proposal envelope and reference semantics

The candidate proposal is an immutable envelope, not a bare DAG: it preserves source/requirement/library/policy pins, selected capsules, objective mappings and budgets. Validation records the proposal reference and publishes the normalized run-plan reference separately. Freeze accepts only that committed validated plan. Exact revised entry fields must be reconciled with the existing service schema; no fixed-template production bypass remains current architecture.

## Wire-contract reconciliation

[Services v1](../contracts/services-v1.schema.json) and the [run-plan owner](../types/run-plan.md) retain existing wire definitions. Their former Brief/experimental-only entry and fixed-template bootstrap must be revised together with accepted intent/requirement ports, profiles, caller permissions, configuration and fixtures. This page specifies the corrected authority/sequence without pretending those old examples already implement it. The previous exact request design is retained as historical source, not current dispatch authority.

[Control flow](../m1/control-flow.md) owns the diagrams and remaining connected revision. [Model authentication](model-auth.md), [environment](environment.md), [library](../capsule/library.md), [storage](storage.md) and [lifecycle](lifecycle.md) retain their protected provider, custody and recovery boundaries.
