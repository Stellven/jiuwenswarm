---
type: home
tags: [index]
---

# Capability Capsule and its core schemas

This package describes **Capability Capsule (CC)** and its core schemas, plus the designs that use them. It is a draft for review.

A **capability capsule** (能力胶囊) is one capability the system can run, described by a **Declaration** and referred to by the hash of its code. Start with [Capability Capsule](capsule/capsule.md): the `capsule/` folder alone explains what CC is, why it exists, and everything it connects to.

Open this folder as an Obsidian vault, or read the Markdown files directly. All links are relative. Each fact is stated on one page and linked from the others.

## Reading order

0. [What architecture covers](architecture.md): the layer between the PRD and the code.
1. [Capability Capsule](capsule/capsule.md): what a capsule is, its kinds and rules, what it connects to, and the index of the capsule folder.
2. [Why CC](capsule/why.md), then the [Declaration](capsule/fields.md): what a capsule holds, every field. To write one: [authoring a capsule](capsule/authoring.md).
3. [Composition](capsule/composition.md), [library](capsule/library.md), [trust](capsule/trust.md), [RSI](capsule/rsi.md), [generalist](capsule/generalist.md), [permissions](capsule/permissions.md), [Symphony](capsule/symphony.md), [tools](capsule/tools.md), [checked and unchecked at M1](capsule/stages.md).
4. [Schemas](schemas/schemas.md): the records kept about a capsule (Candidate, Verdict, Standing, Binding, Observation, Artifact, Verification, Finding), with checks, port types, the policy and the invariants.
5. [B1: the first working pipeline](b1-design.md): the earliest form, with one task-specific capsule. Preliminary.
6. [The M1 design](m1-design.md): the whole of M1 as the PRD sets it, with CC placed in it. Draft, open to change.
7. [The big picture](big-picture.md): a potential near-term goal, open to change, and how each workstream fits.

## Other folders

- `background/`: [terms](background/terms.md) and context. Nothing there needs review.
