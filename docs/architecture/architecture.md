---
type: home
tags: [architecture]
---

# What architecture covers

Architecture sits between the PRD and the code.

| Layer | Says | Detail |
|---|---|---|
| **PRD** | what the product must do, and by which milestone | features, stages, scope |
| **Architecture** | which code modules exist, what each one does, and how data flows between them | modules, schemas, interfaces, APIs |
| **Code** | how each module does it | the implementation |

## The unit is a code module

A module is small enough to become one issue that a coding agent can build on its own. So each module is:

- **Independent.** It depends on other modules only through a declared interface, never on their internals.
- **Separable.** It can be built, replaced or removed without changing the modules around it.
- **Testable in isolation.** Its inputs and outputs are typed, so it can be tested against fixtures, without the rest of the system running.

## What architecture is responsible for

Modules are separate, so everything that connects them belongs to architecture:

- **Schemas:** the data types that pass between modules, and the records they keep. See [schemas](schemas/schemas.md).
- **Interfaces and APIs:** what each module takes and gives, and the calls between them.
- **Data flow:** which module produces each object and which module consumes it, in order.
- **Rules at the seams:** checks and gates that decide whether data may move on, and who is allowed to write each record.

Architecture does not decide how a module works inside. That is the issue's job.

## Capability Capsule is cross-cutting

Muk owns both this architecture and Capability Capsule (CC). That pairing fits because CC supplies the shared execution, schema, gate, record, and adapter contracts used across the project. The architecture defines those contracts once and maps each workstream's capabilities onto them, so independently built modules connect through known interfaces.

CC ownership does not transfer another workstream's product decisions to architecture. The owning workstream defines its stage semantics, domain rubric, and acceptance intent; architecture records the canonical payload/API shape and CC seam that realizes them. An unresolved owner decision stays explicit and blocks only the modules that depend on it.

## Level of detail

- A design page shows modules and data flow, as in [B1](b1-design.md): each node has a named input, a named output and a pass condition.
- A module is ready for an issue when three things are fixed: its input and output types, the checks its output must pass, and the modules on either side of it.
- An issue names its module, its interface and its tests. It never needs another module's internals.

## Code citations

Most modules sit on top of jiuwenswarm, agent-core or deepsearch. Every claim about what that existing code does is a citation, not a description from memory or from what a name suggests.

- **Cite `path:line` at a stated commit, never a branch.** A branch moves; a commit does not. As in `agent-core `e23806c1`` or `jiuwenswarm `bf0e8af7``.
- **A dependency's own pin is authoritative.** jiuwenswarm pins agent-core to an exact commit (`pyproject.toml:20`). When a citation was read at a different commit because the pin was not available locally, mark it **[pin]** and name both commits. Grep the vault for `[pin]` to find every one still owed a re-check.
- **Never cite a working tree's live state.** `huawei/jiuwenswarm` on `ai4r_main_branch` is a docs-focused branch; as of 2026-09-30 it is 23 commits behind and 24 ahead of `origin/AI4Research-Main`, the default branch. Reading whatever happens to be checked out there is not the same as reading current jiuwenswarm. Read an explicit commit (`git show <sha>:path`) and name it.
- **Unverifiable is Open, never asserted.** A file that cannot be found, a pin that cannot be resolved, or behaviour that is unclear from the source goes in the page's Open section as unverified. It does not become a claim because the PRD or a module's name implies it.
- **Read, never edit.** Reading jiuwenswarm, agent-core or deepsearch source to ground a module spec is expected. Changing that source is not architecture's job; it happens through the Code SOP's TASK to Spec Kit process in the working repo.

**Standing item:** the agent-core pin (jiuwenswarm's `9e339019`) is now available locally (`huawei/openjiuwen/agent-core`), 49 commits ahead of `e23806c1`, the commit every current `[pin]`-marked citation was read at. The pin is checkable now; none of the existing `[pin]` citations have been re-checked against it yet.

## Why it matches Capability Capsule

Muk holds both roles, architecture and Capability Capsule, and structured architecture to fit CC. A module spec and a capsule Declaration are much the same thing:

- **A Declaration is an in-depth spec of what a component should do:** what it takes and gives, what it needs, what it changes and what it promises. Its checks are its tests.
- **A capsule is not one file of code.** It is usually many files and related parts. What makes it one unit is that it does one task, with a declared blast radius and declared effects (`changes.effects`, `effect_class`).
- **That is roughly the size of a module.** A module is one task, with typed inputs and outputs and a known reach, that one issue can build and test in isolation.

So a module can be specified the way a capsule is declared, and a capsule is a module whose spec is machine-checked. See [Capability Capsule](capsule/capsule.md).
