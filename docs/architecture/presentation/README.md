# Presentable architecture: claims with reasons

This is the communication layer for reviewers and sponsors. [Architecture authority](../policies.md) and linked owner pages govern implementation. These lines may be used in a brief or deck; they introduce no new requirements. [Diagram atlas](../system/diagram-atlas.md) supplies shallow and deep views.

## A two-minute explanation

**We give each builder an explicit agreement.** Capability inputs, outputs and checks have canonical schemas, so independently built modules can connect without guessing. We borrow the typed component interface pattern documented by [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/). [Our production plan](../m1/pipeline.md) applies it to governed research capabilities.

**We make progress depend on recorded evidence.** A successor runs only after the output, Gate decision and release are committed. We borrow durable execution-history principles from [Temporal](https://docs.temporal.io/workflow-execution); our architecture specifies its own store and supervisor. [Our lifecycle](../system/lifecycle.md) defines the failure and restart rules.

**We keep deployment simple and permissions explicit.** One Dockerized application exposes local user interfaces and benchmark endpoints. Restricted internal processes protect credentials and hidden fixtures. [Docker's security documentation](https://docs.docker.com/engine/security/) explains the namespace and capability foundations; [our deployment](../system/deployment.md) adds the specific inner boundaries and validation obligations.

**We separate improvement from production authority.** RSI evaluates isolated candidates; admission records assurance; a developer activates an admitted version for future runs. This borrows version/alias separation from [MLflow's registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/). [Our library](../capsule/library.md) keeps existing runs pinned.

**We let a model propose and a deterministic boundary decide what can execute.** The isolated planner chooses admitted capabilities through the Codex abstraction; validation checks the complete proposal against types, policy and bounds. [Our planner](../system/planner.md) cannot rewrite a live plan. Production starts with its fixed plan.

**We review both sides of each connection.** Independently derived producer and consumer expectations are compared, following [Pact's contract-testing pattern](https://docs.pact.io/). [Our verification surface](../system/verification.md) also names persistence, timeout, forbidden-access and recovery scenarios.

## What is distinctive about our combination

Typed components, durable evidence, registry versioning and confined execution serve different needs. We connect them through one shared CC declaration and Gate authority. That combination is our design contribution. External precedent supports the borrowed pattern; it is neither endorsement nor proof that our implementation works.

## What can be claimed now

The contracts, ownership map, walkthroughs and documentation checks can be inspected today. [Work checklist](../reviews/2026-10-05-work-checklist.md) records this pass's extent. Real workflow success, measured speed/cost improvement, account compatibility and sandbox security require downstream execution evidence. Use "designed to" for those outcomes until observations support stronger wording.

Avoid claims of an unbreakable system, company equivalence, proven quality or a performance improvement without measurements. Pair each design claim with its owner link and the relevant evidence status.

## Current architecture report

[Seven-page bullet report](architecture-report-2026-10-05.md) summarizes the architecture, CC inventory, borrowed patterns and validation limits. Its [review record](../reviews/2026-10-05-architecture-report-review.md) records source findings and PDF checks. This dated view never overrides canonical contracts.
