---
type: reference
tags: [reference, index]
---

# Terms

Terms used in `read/`, and where each is defined.

## The capsule

| Term | What it is | Where |
|---|---|---|
| **Capability capsule (CC, 能力胶囊)** | one capability the system can run, described by a Declaration and referred to by its code's hash. "CC" also names the schema | [capsule](../capsule/capsule.md) |
| **Declaration** | the capsule's contract: identity, ports, needs, changes, guarantees. The one record the author writes | [declaration](../schemas/declaration.md) |
| **Kind** | the form of the capability: `tool`, `skill`, `prompt_section`, `mcp`, `a2a`, `subagent`, `agent_template`, `composite` (unchecked). | [capsule](../capsule/capsule.md#kinds-of-capsule) |
| **Carrier, body, remote, members** | where the code is: one entry point, a list of hashed files, a remote service pinned by endpoint and version, or pinned member capsules | [declaration](../schemas/declaration.md) |
| **`decl_hash`** | hash of the whole Declaration, v1.0 defaults filled in: one version's identity | [declaration](../schemas/declaration.md) |
| **`interface_hash`** | hash of what tests depend on | [declaration](../schemas/declaration.md) |
| **`code_sha256`** | hash of the capsule's code, checked before every load | [declaration](../schemas/declaration.md) |
| **Port, port type** | a named, typed input or output; every type has a check | [port types](../schemas/port-types.md) |
| **Predicate, `needs.when`** | a precondition on the state | [declaration](../schemas/declaration.md) |
| **Effect class** | the author's promise about state and undo, from `pure` to `irreversible` | [declaration](../schemas/declaration.md) |
| **Failure mode** | a declared way to end without an output (`guarantees.failure_modes`). Any other exception is `CAPSULE_RAISED_UNDECLARED` (INV-19, proposed); at M1 an exception is `CAPSULE_ERROR`. Unchecked at M1 | [declaration](../schemas/declaration.md) |
| **Lineage** | each version's `parent_hash` and `relation`; `merges` with `co_parent_hashes` makes the tree a graph | [declaration](../schemas/declaration.md) |
| **Composite, fusion** | a capsule that pins other capsules as `members`; fusion would rewrite them into one pass (a proposal) | [composition](../capsule/composition.md) |

## Milestone marks

| Term | What it is | Where |
|---|---|---|
| **M1** | the PRD's first milestone. Every field row has an M1 column | [stages](../capsule/stages.md) |
| **checked** | required for M1 and tested for M1 completion | [common](../schemas/common.md) |
| **unchecked** | in the shared schema: type-checked and hashed when present, but not required or tested for M1 | [common](../schemas/common.md) |
| **Unlocks** | names what reads an unchecked field, such as RSI or budgets | [stages](../capsule/stages.md) |

## Records and rules

| Term | What it is | Where |
|---|---|---|
| **Candidate** | a submission: Declaration, files, tests | [candidate](../schemas/candidate.md) |
| **Check** | one runnable test of one target | [checks](../schemas/checks.md) |
| **Test case, test suite** | an input with its expected result; a hashed set of them | [checks](../schemas/checks.md) |
| **Verdict** | admission's decision on a Declaration, with the checks run | [verdict](../schemas/verdict.md) |
| **Standing** | the log of which version of a name is current, and its state. Names are local to a library; `decl_hash` is global | [standing](../schemas/standing.md) |
| **Binding** | the pin for one call site of a run: version, checks, budget, verifier | [binding](../schemas/binding.md) |
| **Artifact** | a stored value. Every capsule output is one | [artifact](../schemas/artifact.md) |
| **Observation** | one capsule call: its `caller`, inputs, outcome and cost | [observation](../schemas/observation.md) |
| **Verification** | the gate's record for one `dispatch` call: which checks ran on its output, and the `decision` | [verification](../schemas/verification-record.md) |
| **Finding** | an observation about capsules, judges or an unmet need. Unchecked at M1 | [finding](../schemas/finding.md) |
| **Finding (measurement)** | a Finding of kind `measurement`: cost, latency or pass rate measured from Observations, never authored | [finding](../schemas/finding.md) |
| **Policy** | every rule, default and registry, as a pinned epoch | [policy](../schemas/policy.md) |
| **Invariants** | the rules every schema obeys | [invariants](../schemas/invariants.md) |

## Tools

| Term | What it is | Where |
|---|---|---|
| **Control code** | code that decides. Never a capsule | [capsule](../capsule/capsule.md#rules) |
| **Author kit** | checks and hashes a draft Declaration before submission | [tools](../capsule/tools.md) |
| **Admission** | checks a Candidate, runs its tests, writes the Verdict and Standing | [tools](../capsule/tools.md) |
| **Runner** | the one path for every capsule call | [tools](../capsule/tools.md) |
| **Check runner, gate** | a check runner runs checks on an output; the gate folds the results into `pass`, `fail` or `blocked` | [tools](../capsule/tools.md) |
| **Librarian** | keeps Standing current from evidence | [tools](../capsule/tools.md) |
| **RSI** | recursive self-improvement: code that builds new capsule versions from evidence. Built on a separate branch that shares the schema | [fields](../capsule/fields.md#how-rsi-uses-a-capsule) |
| **Remover** | retires or revokes a capsule; each effect's `undo` is text, applied by a person or a later tool | [tools](../capsule/tools.md) |
| **Selection index** | finds capsules by summary and port type. It picks capsules, never models: a model, and any routing of it, is inside a capsule, the author's choice | [tools](../capsule/tools.md) |
| **Importer, sandbox** | an importer turns an outside skill, tool, MCP server or A2A agent into a Candidate; the sandbox verifies it in isolation | [tools](../capsule/tools.md) |

## openJiuwen pieces named in `read/`

| Term | What it is |
|---|---|
| **openJiuwen, agent-core** | the open-source agent framework; agent-core is its runtime library |
| **jiuwenswarm** | the multi-agent application built on agent-core |
| **Swarmflow** | agent-core's workflow engine; a workflow is a Python script calling `agent()` |
| **Symphony** | agent-core's capability index, retrieval and planner |
| **jiuwenbox** | a Linux sandbox service for running tools and code in isolation |
| **Agentic Hub** | openJiuwen's self-hosted skill store (the `skillhub` repository) |
