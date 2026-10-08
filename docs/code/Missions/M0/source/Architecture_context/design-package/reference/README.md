# Architecture reference

**Reading level: AI reference.** This layer standardizes consequential information for agents; humans start at [the package README](../README.md). Fields and schemas are architecture, not deferred independent inventions. Use the [contract index](contract-index.md) to find each schema, field definition, producer, consumer and available example.

| Reference | Purpose |
|---|---|
| [Intent and Requirements](intent-and-requirements.md) | Distinct intermediates, required information, checking and consumer rules |
| [Checking and gate records](checking.md) | Mechanical results, semantic verdicts and protected control decisions |
| [CC fields](../capsule/declaration.md) | Current complete reusable declaration; supported execution styles and source reconciliation |
| [Node/subnode contracts](node-execution.md) | Enclosing field contract and critical protected subnode bindings, authority, limits and dispatch identity |
| [Named field catalog](field-catalog.md) | Required field names/types and resolvable public contract IDs |
| [Other major contracts](other-contracts.md) | Plan/node, research, manifests/runtime, model/client and RSI fields; no exhaustive schema library |
| [Catalog](catalog.json) | Versioned schema identities, producer/consumer and examples |
| [Readable examples](examples/README.md) | Small worked set; accepted, blocked and scientific-negative outcomes |

## Schema and manifest principles

1. A shared artifact has one current field contract, an explicit version and named producers/consumers. JSON Schema Draft 2020-12 governs the seven critical schemas. All references resolve through the local catalog; validation needs no network fetch.
2. Required fields communicate obligations. A nullable value or empty list means explicitly absent/not applicable, not an inferred pass. Describe missing/invalid/uncertain outcomes. Not every optional parameter is required before Intent can advance.
3. Closed core fields prevent incompatible inventions. Optional `ext` keys are producer-namespaced diagnostic data; they cannot change meaning, permissions, requirements or gate authority. Contract-breaking changes require a new version and consumer reconciliation; examples do not create another format.
4. Payload bodies contain substantive content plus format version and source references. The trusted runner attaches run/node/attempt, producing invocation, exact byte hash, schema identity, effective configuration and audience in an artifact envelope. Model-supplied runtime identity is never trusted.
5. `Ref {id, sha256}` identifies exact immutable bytes; the manifest maps it to role, format version and descriptive readable path. Runtime checks resolve and validate expected type/version and scope. A hash is not proof of truth or permission. See [inspection](../artifact-inspection.md).
6. Schemas check structure; protected semantic criteria check meaning and usability. Source-span bounds are deterministic; source support and paraphrase fidelity need semantic review. A model readiness flag cannot release work.
7. Keep assessment verdicts, scientific conclusions, library admission and protected gate decisions separate. Valid JSON from an unauthorized writer never becomes protected state.
8. Fixed work has contracts/profiles chosen before execution. Bind complete context before checks; freeze criteria before observations. Do not cache/reuse an old acceptance decision for new evidence.
9. Human-readable JSON and a derived view remain inspectable without anonymous binaries. Raw traces, executable packages and protected RSI fixtures have separate roles and audiences; manifest indirection cannot hide substantive IRs.

## Current critical schemas

The catalog contains CC declaration, Intent IR, Research Brief, deterministic check result, verifier assessment, gate decision and Subnode Execution Contract, plus shared definitions. Other major types have field contracts rather than exact machine schemas. This deliberately replaces the interrupted 60-contract draft. Internal algorithms, adapters, transport routes and classes remain implementation choices.

The examples are synthetic teaching data, not observed runtime evidence. [Design review](../coverage.md) records actual downloaded ZIP observations separately. No historical schema, source maturity label or example grants executable support for future composition/RSI features.

## Architecture standardization revisions

October 7 design-integrity review clarifies field-contract requirements for opportunity statements, deterministic tie handling, route registry/selection records and fully pinned provisioning. Exact schema bodies remain unchanged at 1.0.0. These are pre-implementation clarifications of the current M1 contract set, not a claim that existing implementations are compatible. Native interface agreements must incorporate them; a later change to an implemented field meaning requires an explicit compatibility/version disposition.


October 8 contract review adds the previously prose-only Node Execution Contract at version 1.0.0, complete bindings/examples and named field contracts. The six existing schema bodies remain unchanged. Newly standardized shared field representations are not asserted compatible with prior agent implementations. Native agreements must reconcile them; referenced example byte identities change and previous example evidence becomes stale. [Decision reasoning](../decision-review.md) records alternatives and consequences.

## Field tables first

Required information, meaning, consumer, ownership and failure behavior belong in concise tables. Exact schemas are reserved for critical cross-agent serialization and authority: Intent IR, Research Brief, declaration and execution/verification records. Do not generate a schema for every datatype. Implementation agents select private representations and types within the shared contract; changing consequential interchange requires one reconciled interface agreement.

October 8 node/subnode revision: Research Brief and gate schemas are `2.0.0`; the old CC-sized node schema is replaced by the explicit Subnode Execution Contract `1.0.0`. The enclosing node is a field contract, not another large JSON schema. Other public fields are versioned individually. Earlier receipts above describe earlier inputs and do not claim compatibility with this revision.
