---
type: home
tags: [index]
---

# Capability Capsule and its core schemas

This package describes **Capability Capsule (CC)**: what a capsule is, the schemas that describe it and the records kept about it, and the tools CC uses. It is a draft for review. Its one design page, the M1 design, is a draft open to change.

A **capability capsule** (能力胶囊) is one capability the system can run, such as a tool, a skill or an MCP tool, described by a **Declaration** and referred to by the hash of its code. CC is the schema plus the rules for it. Tools read the schema and write records; CC itself runs nothing.

Open this folder as an Obsidian vault, or read the Markdown files directly. All links are relative.

## Reading order

0. [What architecture covers](architecture.md): the layer between the PRD and the code. Code modules, data flow, schemas and interfaces.
1. [Capability Capsule](capsule/capsule.md): what a capsule is, where CC is going, the rules, and a capsule's life.
2. [Schemas](schemas/schemas.md) and the schema pages it lists: the Declaration, the records kept about a capsule, the policy and the invariants.
3. [What each field is for](capsule/fields.md): which Declaration fields serve verification, RSI, selection and observability.
4. [Tools](capsule/tools.md): the tools CC uses and should have, what each reads and writes, and whether M1 needs it.
5. [Checked and unchecked at M1](capsule/stages.md): the schema is whole from day one. M1, the PRD's first milestone, requires and tests the checked fields; the unchecked fields unlock tools beyond it.
6. [Composition](capsule/composition.md): capsules built from capsules. Unchecked at M1.
   - [When good capsules are bad together](capsule/interactions.md): screening capsule sets with MCTS over their Declarations, after SkillFuzz. Unchecked at M1.
7. [B1: the first working pipeline](b1-design.md): the earliest form. The general pipeline (intake, intent, requirement, pass-through planner and freeze, dispatch, delivery) with one task-specific capsule, `count_spaces`. Preliminary.
8. [The M1 design](m1-design.md): the whole of M1 as the PRD sets it, with CC placed in it and where each schema is used. Draft, open to change.
9. [A possible first design](first-design.md): how the fixed pipeline could run on today's jiuwenswarm code.
10. [The big picture: where we are heading](big-picture.md): a potential near-term goal, open to change. Context for why M1 builds what it builds, and how each workstream fits.

## Other folders

- `background/`: [terms](background/terms.md) and context. Nothing there needs review.
