# Intention Compiler: supporting architecture context

**Architecture Design Context.** Read the [Main entrypoint](README.md) first. Completion requires released `Research_Brief.json` or an attributable halt. The following content is specifically relevant to this node even when shared with other features. Read only the assigned package; do not consult the other experiment condition.

## Required reading by dependency

| Read | What the implementer must take from it |
|---|---|
| [Package overview](../../README.md), [system architecture](../../m1-design.md), [principles](../../principles.md) | Full M1 purpose, authority, deployment and future boundaries; compiler is one node in a larger research system |
| [Compiler behavior](../../intent-design.md), [Immediate Plan](../../immediate-plan.md) | Full producer → checks → verifier → gate sequence; current build ends at Brief |
| [Intent/Brief fields](../../reference/intent-and-requirements.md) | Required information, why consumers need it, missing/default behavior and exact critical schemas |
| [Node/subnode contracts](../../reference/node-execution.md), [field catalog](../../reference/field-catalog.md) | Enclosing objectives versus one-CC assignments, ports, authority and evidence scope |
| [CC declaration](../../capsule/declaration.md), [execution and verification](../../capsules.md), [guard assignment](../../guard-design.md) | Capsule fields/styles, fixed admission pins, independent criteria, protected review context and terminal verifier checks |
| [Checking records](../../reference/checking.md), [failure policy](../../failure-and-human.md) | Complete findings, exact subjects, durable acceptance, no-output halt, correction/cancellation/restart |
| [Placement](../../placement.md), [model routing](../../model-routing.md) | Bundled frontend/runtime, protected credentials/IPC, static model access, aggregate limits |
| [Inspection](../../artifact-inspection.md), [client boundary](../../automation.md), [runtime fields](../../reference/other-contracts.md#manifest-and-runtime-records) | Readable records, authenticated observation/export and durable evidence ownership |
| [Worked examples](../../reference/examples/README.md), [verification obligations](../../reference/compiler-verification.md) | Positive/negative expectations, reference relationships and component test intent |

Follow the listed documents' relevant schema/field links. Field tables are the normal design contract: required information, meaning, producer/consumer and failure behavior. Exact JSON is reserved for critical compatibility/authority boundaries. Agents choose private classes, helper types, routes and storage details within these obligations. They must not silently invent competing shared fields.

## Conditional and future context

| Context | Use now / exclusion |
|---|---|
| [Research responsibilities](../../research-design.md) and [workflow](../../workflow.md) | Understand what the Brief must support; do not build downstream research stages |
| [Delivery phases](../../delivery-phases.md) and [stage exits](../../phase-details.md) | Separate component completion from Stage 2 graph initialization/full M1; Phase 3 is an integration seam |
| [Offline RSI](../../offline-rsi.md) | Preserve immutable contract/check ownership and future eligible implementation boundaries; no RSI execution in this build |
| Scientific execution confinement in placement | Preserve credential/control boundaries; no experiment executor is needed for compilation-only work |
| Sidecar/development tools | Optional ordinary-client compatibility context only; not a build/startup dependency |
| Historical source documents | Provenance only when resolving a cited decision; not competing current schemas |

## Source precedence and bounded choices

The external PRD Main Body owns product obligations; its Context contributes relevant functional context. This package owns implementation-facing architecture and records D5's fixed multi-pass exception to §§3.2/4.7. Resolve an actual product-obligation contradiction explicitly; do not interpret the word “one-shot” as permission to omit Requirements or verification.

Input directory qualification is deterministic, not semantic readiness. A configured empty default document directory is permitted; specified required unreadable inputs halt. Qualified resources remain separate from extracted reference text. The compiler cannot claim that a default `single_gpu` profile proves GPU availability.

Field IDs/types, policy sources, accepted states and authority are consequential shared obligations. Private encodings and algorithms can vary where their meaning, interchange and verification stay compatible. The reference validator establishes documentation/example consistency, not operational security, semantic quality or full implementation acceptance.
