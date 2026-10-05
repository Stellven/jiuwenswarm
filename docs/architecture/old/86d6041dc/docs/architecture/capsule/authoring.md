---
type: capsule
tags: [capsule, guide]
---

# Authoring a capsule

How to turn a tool you have into a capsule. Most capsules are **singletons**: one capability, one node. The fields are defined on the [Declaration](fields.md) page; this page is the order to fill them in. The [example Declaration](fields.md#example) is a finished singleton for a small tool.

## Before you start

- **Declare first.** Write what the tool promises before you polish the code. The tests bind to the interface, not to one implementation.
- **One capability per capsule.** If your tool does two unrelated jobs, make two capsules.
- **Name no task.** A capsule says what it does, never which workflow step uses it.

## Steps

1. **Identity.** Choose a stable `identity.name` (such as `doc.pdf_to_text`) and the `kind`: `tool` for a function, `skill` for a Markdown skill. Point at the code: `carrier` with the file and symbol for one file, or `body` listing every file for a folder. Write a `summary` of at most 400 characters on what it does.
2. **Ports.** List every input and at least one output, each with a type from the [port type vocabulary](../schemas/port-types.md). A `json` port needs its JSON Schema, pinned by hash. Give every output a `check_id`.
3. **Needs.** Write the preconditions that must hold before a call (`needs.when`), the other capsules it calls (`needs.external`, each pinned to an admitted version), and the network access it needs. For a dependency you would like kept up to date, write its `purpose` in a sentence. List packages with a lockfile.
4. **Changes.** State the `effect_class`, from `pure` to `irreversible`, and list each effect on the world with its `resource_key` (such as `fs:workspace/out/*`) and whether it can be undone. When unsure, choose the less reversible class.
5. **Guarantees.** Write at least one check for each output: what passes, the code that runs it, and whether it needs a known answer (`admission`) or can check any live output (`node`). A check that can be written as code should be.
6. **Test cases.** For every `admission` or `both` check, give at least one input and its expected result. A tool that reads outside state ships fixtures so its tests do not depend on the outside world.
7. **Failure modes only when they add information.** Do not repeat missing-port, schema, timeout, permission, effect or standard runtime failures. Add a failure mode only when it names a capability-specific hazard the runner or Gate can enforce or classify; add the corresponding verification case in the same Candidate.
7. **RSI permission.** Set `evolution.rsi`: `none` if RSI may never change it, `propose` if a person should approve each change, `submit` if an admitted child may replace it. If not `none`, list in `evolution.may_change` exactly what RSI may change, such as `files:SKILL.md` for the prompt; RSI may change nothing else. A capsule that will act as a gate or verifier must be `none`.
8. **Skills: write the prompt brief.** A model-backed capsule carries a [prompt brief](prompt-brief.md), so the layer that writes `SKILL.md` has what it needs.
9. **Check locally.** Run the author kit: it checks the Declaration against the schema and the policy, hashes every file, computes `decl_hash`, `interface_hash` and `code_sha256` ([fields](fields.md#computed-by-admission-never-written-by-the-author)), and runs the admission checks on your test cases.
10. **Submit.** Submit a Candidate: the Declaration, the files and the test cases. Admission re-hashes, applies the rules, runs the tests and writes the Verdict. If a rule fails, the reason code says which ([policy](../schemas/policy.md)).

What happens after admission: [library](library.md). What your capsule is trusted to do: [trust](trust.md). What jiuwenswarm will let it touch: [permissions](permissions.md).

## If the tool comes from outside

For a tool, skill or MCP server from a hub or a repo, the importer drafts the Declaration, checks and test cases from what it can read, and invents nothing. A person then confirms the effects and writes at least one check before it is submitted. One MCP server becomes one capsule per tool. See [tools](tools.md#for-imported-capabilities).

## Common mistakes

- An output with no check, or an admission check with no test case: admission refuses it.
- An `effect_class` weaker than the listed effects: admission refuses it (`EFFECT_CLASS_INCONSISTENT`).
- A summary that names a workflow step: refused (`SUMMARY_NAMES_TASK`).
- Choosing a model in the Declaration: there is no field for it. The model is chosen in the capsule's own files ([details](fields.md#needs-what-must-hold-and-what-it-uses)).
