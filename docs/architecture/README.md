---
type: home
tags: [index]
---

# M1 architecture and shared Capability Capsule contracts

This package describes the complete M1 system design, its **Capability Capsule (CC)** foundation and the shared contracts used by production, offline RSI and isolated experiments. It is a draft for review.

**Status: architecture draft under connected review.** The [October 2 source set](../product/SOURCE_FREEZE.md) is frozen. Draft contracts may change together; a handoff release pins their revisions and generated hashes. Released core versions are immutable. [Policies](policies.md) define AI review, contract revision and evidence requirements; [invariants](schemas/invariants.md#change) define schema compatibility.

A **capability capsule** (èƒ½åŠ›èƒ¶å›Š) is one capability the system can run, described by a **Declaration** and referred to by the hash of its code. Start with [Capability Capsule](capsule/capsule.md): the `capsule/` folder alone explains what CC is, why it exists, and everything it connects to.

Open this folder as an Obsidian vault, or read the Markdown files directly. Links are relative. The [authority index](authority.md) identifies which file owns each definition and how to trace a change. Summaries, stories and diagrams link those owners; historical reviews describe the revision reviewed at that time.

## Explain and review

Start with the [diagram atlas](system/diagram-atlas.md) for shallow and deep views; the [presentable variant](presentation/README.md) gives claim/reason/owner lines. [October 5 work checklist](reviews/2026-10-05-work-checklist.md) records the extent and evidence of this cleanup.

## Build from these

[Stories](stories/README.md) follow concrete items through proposed code, interfaces, Gates and storage, including failure and recovery paths. Their [quality record](stories/quality-checks.md) distinguishes walkthrough/schema checks from executed product behavior.

For coders and the layer that turns design into prompts. Start at [coder requirements](system/coder-requirements.md) and the [full handoff](system/handoff.md), which link every module's seven engineering answers.

[October 3 checkpoint manifest](handoff-checkpoint-2026-10-03.json) pins that captured revision's Git blob bytes. It predates later corrections and is historical evidence, not a hash manifest for the current checkout. [Release evidence](reviews/2026-10-03-release-evidence.md) records those documentation checks; the [stories quality record](stories/quality-checks.md) records later checks and remaining implementation obligations.

1. [Build order](system/build-order.md): one capsule, then one connected capsule, each step with a check someone else can run.
2. [Module placement and process map](system/modules.md), [durable storage](system/storage.md), [system records](system/records.md), [run lifecycle](system/lifecycle.md), [environment and security](system/environment.md), [local workstation](system/workstation.md) and [verification](system/verification.md).
3. [Runner](capsule/runner.md) and [toolchain](capsule/toolchain.md): how a call runs, and the tool APIs. [Gate host](capsule/gate-host.md) and [gate capsules](capsule/gate-capsules.md).
4. [Payload types](types/types.md) and the generated JSON Schemas in [`exports/`](exports/manifest.json): the one definition of every value that moves between modules. Import the files; never write a type by hand.
5. [The M1 pipeline](m1/pipeline.md): eight governed research steps, shared verifier and reusable search capabilities. [Capsule design packets](m1/capability-designs.md) connect all twelve capabilities to their owning contracts, optimization hypotheses and failure fixtures; [benchmark material](m1/benchmarking-material.md) identifies sources and custody requirements. [Spatial](system/diagram.md) and [temporal](system/temporal.md) diagrams map code boundaries and execution order. [Track isolation](system/experiments.md), [planner](system/planner.md), [offline RSI](capsule/rsi-engine.md) and [benchmark export](system/benchmark-export.md) cover the other paths.
6. [Prompt brief](capsule/prompt-brief.md): the line between this design and the prompt text, and the rows a model-backed capsule page carries.
7. [Seams](seams.md): the API between CC and each other workstream. [Decisions](decisions.md) and [open issues](open-issues.md) say what is settled and what blocks.

These contracts are drafts or provisional until their pages are `checked`; [open issues](open-issues.md) lists the exact owner and platform blockers. The [full run plan](m1/pipeline.md), [measurement protocol](m1/measurement-protocol.md), [research-stage gates](m1/research-gates.md), [offline RSI engine](capsule/rsi-engine.md), [M1 untrusted process boundary](capsule/process-boundary.md) and [RSI fixture oracle](capsule/fixture-oracle.md) connect them.

## Understand the design

**Deployment agreement:** [one Dockerized modular monolith](system/deployment.md), with [authenticated benchmark HTTP endpoints](system/benchmark-export.md#docker-http-transport). Linux Engine and macOS Docker Desktop use the same Linux image; restricted internal processes retain security boundaries.

[Model authentication](system/model-auth.md) chooses a dedicated persistent Codex home and separate container login, with replaceable auth/inference adapters. [Final fresh review](reviews/2026-10-03-final-fresh-review.md) records source-verified findings and their dispositions; [verification](system/verification.md) distinguishes architecture checks from required runtime evidence.

In reading order:

0. [What architecture covers](architecture.md): the layer between the PRD and the code. Then [the system layer](system/overview.md): where CC fits, [nodes](system/nodes.md), [integration with existing code](system/integration.md), [observability](system/observability.md) and [ledgers](system/ledgers.md).
1. [Capability Capsule](capsule/capsule.md): what a capsule is, its kinds and rules, what it connects to, and the index of the capsule folder.
2. [Why CC](capsule/why.md), then the [Declaration](capsule/fields.md): what a capsule holds, every field. To write one: [authoring a capsule](capsule/authoring.md).
3. [Composition](capsule/composition.md), [library](capsule/library.md), [trust](capsule/trust.md), [RSI](capsule/rsi.md), [generalist](capsule/generalist.md), [permissions](capsule/permissions.md), [Symphony](capsule/symphony.md), [CC tooling and field enforcement](capsule/tools.md), [checked and unchecked at M1](capsule/stages.md).
4. [Schemas](schemas/schemas.md): the records kept about a capsule (Candidate, Verdict, Standing, Binding, Observation, Artifact, Verification, Finding), with checks, port types, the policy and the invariants.
5. [Design order](m1/order.md), [full PRD coverage](prd/coverage.md) and [exact clause inventory](prd/clause-inventory.md). The [frozen source set](../product/SOURCE_FREEZE.md) replaces file-date precedence. Earlier PRD reviews and the inventory proposal are historical and do not define current behavior.
6. [The big picture](big-picture.md): a potential near-term goal, open to change, and how each workstream fits.
7. [Model routing](model-routing/README.md): CC decides what is done; routing is an optimization inside a capsule.

**Validation still required:** [implementation and platform obligations](open-issues.md). Every M1 responsibility has a published design; specified confinement mechanisms require actual implementation probes before their platform acceptance can pass.

**How this vault is built:** [policies](policies.md) own the agreements; [PROCESS](PROCESS.md) owns the procedure. From this folder, `python _tools/arch_lint.py` regenerates [`exports/`](exports/manifest.json) and the [design graph](graph.md); `python _tools/arch_lint.py --check` verifies they are current without writing. Reviews are in [`reviews/`](reviews/2026-10-02-build-readiness.md).

## Past designs

The historical checkpoint and its reproducible check results are in [release evidence](reviews/2026-10-03-release-evidence.md). [Boundary cases](system/boundary-cases.md) gives the coding team invocation points and expected outcomes without claiming executed implementation results.

Kept in [`archive/`](archive/m1-design.md) as a record only. They are not current; do not build from them.

- [The M1 design](archive/m1-design.md), proposed 2026-09-28.
- [M1 architecture](archive/m1-architecture.md), the 27-module build draft written against PRD section 3. Superseded by the pages above. Its module ids (M01, M03, ...) survive as names; the [handoff page](system/handoff.md#complete-module-cards) says which are current.
- [B1: the first working pipeline](archive/b1-design.md), the earliest form, with one task-specific capsule.
- [First PRD review](prd/prd-review.md), against the initial PRD. Superseded by the full PRD review.

## Other folders

- `exports/`: JSON Schemas generated from the field tables. Never edit by hand.
- `model-routing/`: CC's reply to the Model Routing design, and `model_router_design_en.md`, that team's design, kept verbatim.
- `data-foundation/`: the Data Foundation team's design, kept verbatim.
- `background/`: [terms](background/terms.md) and context. Nothing there needs review.

## Outside this repository

- **Schema drafts and derivations**: `huawei/capsule-openjiuwen/` (scratch and build, not the vault; finished pages move here).
- **Presentation renders**: `huawei/mermaid-renders/` (PNG/SVG) and `huawei/slides-png/` (deck-to-PNG exports). Both are generated output, not source; see each folder's README for what generates them and from where.
- **Notes**: `tundle/obby/` (Muk's notes; never the design itself).
