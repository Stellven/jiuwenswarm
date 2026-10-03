---
type: design
status: draft
version: 1
owner: muk
sources: [../product/SOURCE_FREEZE.md, ../product/coder-architecture-requirements-2026-10-02.txt, PROCESS.md]
provides: [architecture.policies]
consumes: []
depends_on: []
tags: [policy, review, sources, handoff]
---

# Architecture authoring and review policies

The architecture is the coding team's shared agreement. The frozen master PRD sets scope; owner designs supply domain detail; architecture decides shared interfaces. Preserve received documents and record each reconciliation in [decisions](decisions.md). Routine interface design does not wait for owner permission.

## Small, replaceable modules

Create a capsule when independent reuse, admission/versioning, governed model work or a distinct permission boundary needs a Declaration. Otherwise use an ordinary module with a public typed function. Capsule count is an outcome, not an acceptance target. Orchestration selects work; capsules perform their declared capability; model routing selects an endpoint within permitted experimental settings. Types cross boundaries; internal algorithms stay with the implementer.

Every substantial decision cites a primary software or paper precedent, identifies the exact pattern borrowed, explains M1 fit and rejected alternatives, and names its replacement interface and trigger. Existing software is inspected at a pin once and recorded in [integration](system/integration.md); repeat inspection only after a changed pin, disproved behavior or affected requirement.

## One owner and controlled change

Schemas, API signatures, errors, configuration keys, record variants and write authority have one owning definition. A module card links that definition instead of copying it. Consumers cannot infer additional semantics from an example or diagram.

Draft contract revisions may change together. A handoff release pins source manifest, architecture commit, generated-schema hashes, configuration/profile versions, module map and review evidence. Once released, any core shape or meaning change creates a new contract version and explicit migration; namespaced `ext` is the existing-version extension boundary. Identify all producers, consumers, gates, records, plans, diagrams and fixtures requiring recheck before editing.

## AI review is the normal review path

People receive a short decision brief; fresh AI reviewers inspect the full evidence. There is no required reviewer model. A reviewer receives the frozen source manifest, the exact claims and owning pages, and affected consumer links, without relying on the author's conclusions.

| Review | Required evidence and output |
|---|---|
| Source compliance | Trace each adopted behavior to exact PRD clauses; flag whitelist expansion and source conflicts |
| Engineering completeness | Answer all seven [coder questions](system/coder-requirements.md); inspect APIs, data ownership, process authority, errors, recovery and replaceability |
| Boundary derivation | Independently derive producer and consumer declarations/fixtures from canonical docs; compare without repairing fixtures to fit implementation |
| Security | Inspect principals, readable/writable paths, IPC, model credentials, hidden material, network/process limits and failure-closed behavior |
| End-to-end review | Walk production, offline RSI and permitted isolated tracks, including temporal failure paths and evidence joins |

Every finding has an ID, severity, exact source/contract evidence, consequence, proposed correction, affected consumers and disposition. The author verifies findings against source before applying them. Resolve disagreements with the canonical requirement and contract evidence; further targeted review is allowed when a material disagreement remains. Re-review affected claims after a fix. A model's approval or repeated agreement alone is not evidence of correctness.

Mechanical schema/link/graph/source-hash checks complement AI review. `checked` records completed architecture checks; `locked` records Muk's approval. Neither claims a working implementation. The human brief lists only scope changes, significant tradeoffs, unresolved disagreements and runtime/security validation obligations.

## No undefined system responsibilities

Every in-scope component receives a concrete module, interface, failure outcome and verification hook. A pending external schema uses a bounded provisional adapter. A mechanism awaiting execution evidence is a specified design with a validation obligation. Unsupported requirements fail closed. Such an outcome does not satisfy the corresponding platform requirement; it stays visible in release acceptance.

## Provenance and clean releases

Commit coherent documentation and generated artifacts after local checks and finding disposition. Stage relevant paths explicitly, inspect the staged diff, exclude credentials and unrelated changes, then fetch before push. Reconcile compatible documentation changes; preserve both sides of semantic conflicts and resolve them against the frozen baseline. Do not overwrite unrelated work or force-push. The user's 2026-10-02 authorization permits these architecture commits and pushes without repeated confirmation.

No implementation, Spec Kit generation or fabricated runtime results belong to this revision. The coding process maps these agreements into its owning TASK and native Spec Kit records.
