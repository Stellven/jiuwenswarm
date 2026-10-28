# Capsule build references

`Tier 3 · Part of: [Reference](../README.md)`

Each page here gives one coding agent what it needs to build one capability capsule (CC) and its verifier assignment without inventing a shared name, field or check. Humans read the [component pages](../../pipeline/README.md) instead.

A page owns the field contracts of the artifacts its CC produces. Other pages link to it and do not restate fields.

| CC | Page | Produces |
|---|---|---|
| Intent | [Intent and Requirements](../intent-and-requirements.md) | `intent_ir` |
| Requirement | [Intent and Requirements](../intent-and-requirements.md) | `research_brief` |
| Planner | [planner.md](planner.md) | `plan_proposal` |
| Search | [search.md](search.md) | `candidate_set` |
| Screening | [screening.md](screening.md) | `screening_result`, `opportunity_card` |
| Hypothesis | [hypothesis.md](hypothesis.md) | `hypothesis_blueprint` |
| Builder | [builder.md](builder.md) | `poc_manifest`, `poc_artifact_bundle` |
| Research Benchmark | [research-benchmark.md](research-benchmark.md) | `benchmark_payload`, `execution_receipt`, `provisioning_receipt` |
| Scientific Evaluation | [scientific-evaluation.md](scientific-evaluation.md) | `evaluation_verdict` |
| Delivery | [delivery.md](delivery.md) | `delivery_manifest`, `research_report` |
| Verifier | [verifier.md](verifier.md) | `verifier_assessment`, plus the `check_bundle` and `checking_profile` contracts |

The run plan contracts (static template, plan proposal binding, frozen run plan and dispatch record) are in [run plan](../run-plan.md).

## Naming rules

Internal names are lowercase only. Docker runs on Linux, where `Research_Brief.json` and `research_brief.json` are different files.

| Item | Rule | Example |
|---|---|---|
| Artifact type | lowercase snake_case noun | `research_brief` |
| Artifact file | artifact type plus extension | `research_brief.json` |
| Port name | lowercase snake_case short role name. A port may use its artifact type or a shorter role name. The Brief port is always `brief`. Two ports of one CC that take the same artifact type need distinct names | `brief`, `candidate_set`, `manifest`, `baseline_resource` |
| Check ID and criterion ID | lowercase snake_case | `score_range`, `declared_output_conformance` |
| Schema check ID | every output port has one blocking schema check named `<port>_schema`. The CC declaration, the check bundle and the page use the same ID | `candidate_set_schema`, `manifest_schema` |
| CC name | lowercase dotted `<area>.<capability>` | `research.screening` |
| Contract ID | existing lowercase kebab IDs stay as they are | `candidate-set:field-contract:2` |
| Enum values | keep the spelling of the owning schema or table | `PASS`, `single_gpu` |

A file the user explicitly names keeps that name. Every other file the system writes is lowercase. The glossary maps PRD spellings (for example `Research_Brief.json`) to these names.

## Page template

Every CC page has these sections in this order. Keep prose short. Tables carry the detail.

The plain-English meaning and constraint of each field are the definition. A reader must be able to write a correct value from the table alone. Examples only illustrate. If an example and a table disagree, the table wins and the example is a defect. Directly under each field table, link its examples: one valid example and any invalid example, with the check that rejects it.

0. **Summary.** Three to five lines a human reviewer can check without reading the tables: what the CC takes, what it produces, what blocks it, what it must never do.
1. **Purpose and place in the run.** One paragraph on what the CC does and takes. Workflow placement does not belong here ([D42](../../method/decisions.md#d42)).
2. **Declaration.** Link the declaration example file `<cc>_capsule.json` (validates against the [declaration schema](../schemas/capsule-declaration.schema.json)). Summarize identity, ports, needs, effect class, budget and the pinned check bundle.
3. **Inputs.** Table: port, artifact type, producer, required, how the CC uses it.
4. **Output field contract.** Table: field, type, required, constraint, meaning. A constraint is an enum, range, length, pattern or cross-field rule. Write "none" only when no rule applies.
5. **Producer obligations.** What the worker must do and must not do. Include its own internal self-review steps. These are not verifier duties.
6. **Deterministic check bundle.** Table: check ID, rule, outcome on failure. The host runs these before the verifier. They may read inputs and runtime records.
7. **Verifier criteria.** Table: criterion ID, question, blocking. The verifier sees only the declaration and the exact output. Every question must be answerable from those two artifacts.
8. **Gate rule.** When the gate accepts, rejects or halts.
9. **Failure outcomes.** Table: condition, outcome, what is kept.
10. **Examples.** Valid and invalid example files, and the check that rejects each invalid one.
11. **Future seams.** What later work this contract must not block.
12. **M1 placement.** The last section. Short. It states where the CC runs in M1, which plan policy entry or binder check enforces it, and nothing else. A CC with no placement rule beyond its ports still has the section.

## Field types

Use the primitive types `string`, `integer`, `number`, `boolean`, `sha256` and `object`, the named types in [field-contracts.json](../field-contracts.json), `T[]` for arrays and `nullable-T` for an explicit null. `Ref` is `{id, sha256}` and points to exact immutable bytes.

Constraint keys in the machine mirror are `enum`, `min`, `max`, `min_items`, `max_items` and `pattern`. The validator enforces them on examples.
