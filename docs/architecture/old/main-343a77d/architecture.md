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

## Level of detail

- A design page shows modules and data flow, as in [B1](b1-design.md): each node has a named input, a named output and a pass condition.
- A module is ready for an issue when three things are fixed: its input and output types, the checks its output must pass, and the modules on either side of it.
- An issue names its module, its interface and its tests. It never needs another module's internals.

## Why it matches Capability Capsule

Muk holds both roles, architecture and Capability Capsule, and structured architecture to fit CC. A module spec and a capsule Declaration are much the same thing:

- **A Declaration is an in-depth spec of what a component should do:** what it takes and gives, what it needs, what it changes and what it promises. Its checks are its tests.
- **A capsule is not one file of code.** It is usually many files and related parts. What makes it one unit is that it does one task, with a declared blast radius and declared effects (`changes.effects`, `effect_class`).
- **That is roughly the size of a module.** A module is one task, with typed inputs and outputs and a known reach, that one issue can build and test in isolation.

So a module can be specified the way a capsule is declared, and a capsule is a module whose spec is machine-checked. See [Capability Capsule](capsule/capsule.md).
