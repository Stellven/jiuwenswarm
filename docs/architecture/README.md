---
type: home
tags: [index]
---

# Capability Capsule and its core schemas

This package describes **Capability Capsule (CC)** and its core schemas, plus the designs that use them. It is a draft for review.

**Status: exploratory alpha and beta.** No schema page here is `v1` yet, every one is still `draft` or `proposed`, so nothing is version-locked. Fields can still move, merge or disappear. `v1` starts once real code for an actual module is being built against a page, not before. See [the invariants](schemas/invariants.md#change) for the exact rule.

A **capability capsule** (能力胶囊) is one capability the system can run, described by a **Declaration** and referred to by the hash of its code. Start with [Capability Capsule](capsule/capsule.md): the `capsule/` folder alone explains what CC is, why it exists, and everything it connects to.

Open this folder as an Obsidian vault, or read the Markdown files directly. All links are relative. Each fact is stated on one page and linked from the others.

## Reading order

0. [What architecture covers](architecture.md): the layer between the PRD and the code. Then [the system layer](system/overview.md): where CC fits, [nodes](system/nodes.md), [integration with existing code](system/integration.md), [observability](system/observability.md) and [ledgers](system/ledgers.md).
1. [Capability Capsule](capsule/capsule.md): what a capsule is, its kinds and rules, what it connects to, and the index of the capsule folder.
2. [Why CC](capsule/why.md), then the [Declaration](capsule/fields.md): what a capsule holds, every field. To write one: [authoring a capsule](capsule/authoring.md).
3. [Composition](capsule/composition.md), [library](capsule/library.md), [trust](capsule/trust.md), [RSI](capsule/rsi.md), [generalist](capsule/generalist.md), [permissions](capsule/permissions.md), [Symphony](capsule/symphony.md), [CC tooling and field enforcement](capsule/tools.md), [checked and unchecked at M1](capsule/stages.md).
4. [Schemas](schemas/schemas.md): the records kept about a capsule (Candidate, Verdict, Standing, Binding, Observation, Artifact, Verification, Finding), with checks, port types, the policy and the invariants.
5. [B1: the first working pipeline](b1-design.md): the earliest form, with one task-specific capsule. Preliminary.
6. [The M1 pipeline](m1/pipeline.md): the run plan, step by step, and the [design order](m1/order.md). The [build order](system/build-order.md) says what is built first and what blocks what. A [smaller capsule inventory](m1/capsule-inventory-proposal.md) is proposed, not adopted. The [full PRD coverage and responsibility map](prd/coverage.md) connects clauses to contract owners and workstreams. The PRD is in [`docs/product`](../product/README.md) (current: the full PRD of 2026-10-01); architecture's [review of it](prd/prd-m1-full-review.md) and the [draft reply](prd/prd-m1-full-reply.md).
7. [The big picture](big-picture.md): a potential near-term goal, open to change, and how each workstream fits.
8. [Payload types](types/types.md): the one definition of every value that moves between modules, and where every other shared datatype is defined.
9. [Seams](seams.md): the API between CC and each other workstream. [Runner](capsule/runner.md) and [toolchain](capsule/toolchain.md): M1 call execution and tool APIs. The [CC tooling map](capsule/tools.md) shows field enforcement and deferred capabilities; [M1 untrusted process boundary](capsule/process-boundary.md) and [RSI fixture oracle](capsule/fixture-oracle.md) define the two distinct provisional code-execution trust boundaries.
10. [Decisions and precedents](decisions.md): authoritative dispositions, borrowed design patterns and replacement triggers. [Open issues](open-issues.md) now contains only unresolved product conflicts and implementation validation.

**What is not finished yet:** [black boxes](system/blackboxes.md), limited to genuine product conflicts or safety mechanisms that cannot yet be validated.

**How this vault is built:** [PROCESS](PROCESS.md). Lint: `python _tools/arch_lint.py --check`. The generated [design graph](graph.md).

## Past designs

Kept as a record only. They are not current; do not build from them.

- [The M1 design](m1-design.md), proposed 2026-09-28.
- [M1 architecture](m1-architecture.md), the 27-module build draft written against PRD section 3. Superseded by the pages above; its module ids (M01, M03, ...) are still used as names.
- [First PRD review](prd/prd-review.md), against the initial PRD. Superseded by the full PRD review.

## Other folders

- `background/`: [terms](background/terms.md) and context. Nothing there needs review.

## Outside this repository

- **Schema drafts and derivations**: `huawei/capsule-openjiuwen/` (scratch and build, not the vault; finished pages move here).
- **Presentation renders**: `huawei/mermaid-renders/` (PNG/SVG) and `huawei/slides-png/` (deck-to-PNG exports). Both are generated output, not source; see each folder's README for what generates them and from where.
- **Notes and decision log**: `tundle/obby/` (Muk's notes; never the design itself).

## Current coding-handoff design

Start with [module placement and process map](system/modules.md), [durable storage](system/storage.md), [system records](system/records.md), [run lifecycle](system/lifecycle.md), [environment and security](system/environment.md), [local workstation](system/workstation.md), and [verification invocation contracts](system/verification.md). The [full run plan](m1/pipeline.md), [measurement protocol](m1/measurement-protocol.md), [research-stage gates](m1/research-gates.md) and [offline RSI engine](capsule/rsi-engine.md) connect them. These additions are drafts/provisional contracts, not approved implementation or completed runtime acceptance. [Open issues](open-issues.md) lists the exact owner/platform blockers.
