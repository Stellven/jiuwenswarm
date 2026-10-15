# Intent IR and Requirements IR

`Tier 3 · Part of: [Reference](README.md)`

**Summary.**
- The Intent CC turns the qualified request into `intent_ir`. The Requirements CC turns accepted Intent into `research_brief`.
- Each CC owns the fidelity and preservation of its own output. It self-reviews, and the host runs deterministic checks on spans, references, link coverage and default authorization.
- The semantic verifier reads only the CC declaration and the exact output. It never reads the request, the Intent, the defaults or any other worker input.
- Verifier criteria for both CCs are in the tables below. Each is answerable from declaration plus output.

[Intent design](../pipeline/intention-compiler.md) explains behavior and rationale. Required core keys below match the exact schemas. All statements need attributable support; no sample is a fill-in prompt template.

## Intent IR

Producer: Intent CC. Consumers: deterministic checker, Intent verifier, then Requirements **only after acceptance**. [Schema](schemas/intent-ir.schema.json).

| Required field | Meaning / type | Why the consumer needs it |
|---|---|---|
| `schema_version` | Current format version | Reject incompatible structures before review |
| `request_ref` | Exact original request reference | Prevent substitution and preserve meaning |
| `interpretation` | The Intent CC's statements `problem`, `desired_change` and `requested_result`, each nullable. A null means the request does not state it. If that leaves Requirements without enough purpose, the IR carries a blocking `missing` uncertainty | Identify purpose and intended output without choosing a scientific solution |
| `context` | IDs, entity name/role and source spans | Make affected entities and supplied context explicit |
| `in_scope`, `out_of_scope` | Attributed statement lists | Bound Requirements and later work |
| `constraints` | ID, text, category and source spans | Preserve limits, prohibitions, time/data/format requirements |
| `preferences` | Attributed statements | Preserve optional wishes without silently elevating them |
| `user_targets` | ID, metric, target text, source spans | Preserve explicit targets; do not invent numeric thresholds |
| `context_refs` | Permitted context/source references | Resolve relevant original material |
| `uncertainties` | ID, kind, description, affected fields, blocking flag, clarification. A blocking uncertainty means `readiness.status` is `needs_clarification` | Distinguish missing, ambiguous and conflicting meaning |
| `readiness` | The Intent CC's own claim, `ready` or `needs_clarification`, with a reason. It is untrusted. `ready` only when no uncertainty is blocking | Explain the worker's candidate-state claim; host gate owns acceptance |

An attributed statement has `id`, `text`, `source_spans`. Each span contains `source_ref`, `start`, `end`; offsets count Unicode code points in exact source text and exclude the end. IDs are unique within the IR; references must be permitted and spans nonempty/in-bounds. Preserve original source bytes before any extraction/normalization and identify the extracted source text separately when relevant.

### Producer obligations (Intent CC)

The Intent CC owns fidelity to the request and usefulness to Requirements. Before it returns output it re-reads its own IR against the request and confirms each point.

1. Every `in_scope` item, `constraint` and `user_target` traces to a source span that supports it. A paraphrase must not add a method, effect, target or number the span does not state.
2. Every exclusion, constraint and preference in the request appears in the IR with its span. Optional methods, hardware and thresholds may stay absent.
3. Entities and scope agree across fields. Contradictory required constraints appear as a blocking uncertainty.
4. `interpretation` gives enough purpose and requested result for Requirements to start without inventing the work. When it cannot, the IR lists a blocking `missing` uncertainty and sets `readiness.status` to `needs_clarification`.
5. `readiness` agrees with `uncertainties`: `ready` only when no uncertainty is blocking.

### Deterministic host checks (Intent)

The host runs these before the verifier. They read the request and runtime records. The check plan is in [check_plan](examples/check_plan.json).

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `intent_schema` | Schema and version match. Required fields are present. Local IDs are unique. | Halt. No verifier call. |
| `source_spans` | Every span names a permitted source, is nonempty and lies inside the exact source text (span bounds). | Halt. |
| `exact_identity` | `request_ref` and every `context_refs` entry resolve to the exact qualified bytes (reference resolution). The invocation completed with the pinned implementation. | Halt. |

### Verifier criteria (Intent)

The verifier sees the Intent CC declaration and the exact `intent_ir` output. Nothing else.

| Criterion ID | Question | Blocking |
|---|---|---|
| `declared_output_conformance` | Does the output have the artifact type, fields and shape the declaration states? | yes |
| `internal_consistency` | Do the fields of the output agree with each other, and do all local ID references resolve inside the output? | yes |
| `limitations_consistency` | Are the listed uncertainties and limitations coherent with the rest of the output? | yes |
| `uncertainty_consistency` | Does `readiness.status` agree with the listed uncertainties (`ready` only when none is blocking)? | yes |

An honest `needs_clarification` IR is valid candidate data. The gate halts on it because readiness is `needs_clarification` or an uncertainty is blocking. The verifier does not create corrected Intent. The host shows the user the clarification text.

Examples: [valid](examples/intent_ir.json) · assessments: [intent_assessment](examples/intent_assessment.json) · declaration: [capsule_declaration](examples/capsule_declaration.json)

## Research Brief / Requirements IR

Producer: Requirements CC within the Intention Compiler node. Consumers: deterministic checks, Requirements verifier, node gate, then static binder/planner and research CCs **after node release**. [Critical schema](schemas/research-brief.schema.json), version `2.0.0`. The external name remains `research_brief.json`; Requirements IR is a descriptive alias, not a second format.

| Required field | Required meaning / information | Why consumers need it |
|---|---|---|
| `schema_version` | Explicit current version | Reject incompatible representations |
| `intake_ref`, `intent_ref`, `context_refs` | Exact qualified intake, accepted meaning and relevant permitted context | Preserve source identity and supplied context without copying every document |
| `domain_lane` | Fixed `scientific_research` baseline | Prevent unintended multi-lane dispatch; later variants need explicit compatibility |
| `objective` | Attributed requirement statement | Define what the research program is asked to achieve |
| `in_scope`, `out_of_scope` | Attributed boundary statements | Constrain search, planning and implementation |
| `mandatory_requirements`, `optional_preferences` | Stable IDs, readable statements, origin and source references | Cover mandatory outcomes without silently promoting/waiving preferences |
| `input_bindings`, `resource_refs` | Named input identity/role/resource reference, plus consistent inventory | Separate reference documents, project assets and validation data; preserve supplied resources |
| `constraints` | ID, readable meaning, category, origin, sources, applicable `scope`, `normalized_value`, `unit`, `operator` | Bind operational/scientific restrictions without downstream text guessing |
| `target_metrics` | ID, metric, target text, origin, sources, linked `requirement_ids`, nullable unit/comparison | Preserve concrete and qualitative user goals; Hypothesis later defines measurement and scientific verdict rules |
| `deliverables` | IDs, names, description and artifact type | Define observable requested outputs |
| `acceptance_expectations` | ID, linked requirements and observable completion meaning | Check that the workflow addresses the user's requested result |
| `evidence_obligations` | ID, linked requirements and evidence meaning | Establish what must substantiate completion |
| `assumptions` | ID, text, protected `authority_ref`, actual affected-field JSON pointers | Make every applied default visible and attributable |
| `unresolved_items` | Missing, ambiguous or conflicting information, each with a blocking or non-blocking disposition. A blocking item prevents acceptance | Block material uncertainty instead of manufacturing requirements |
| `confirmation` | User-request or authorized-assumption basis with sources | Record permission to proceed without asynchronous approval waiting |

Requirement statements contain `id`, `text`, `origin` (`user`, `system_default`, `derived`) and source references. Local IDs are unique. Acceptance/evidence/metric requirement IDs resolve. Derived requirements follow accepted meaning; they cannot introduce a new objective or chosen scientific solution.

Quantitative constraints preserve the stated value, unit and comparison (`lt/le/eq/ge/gt`), plus compiler/run/scientific-execution scope. Categorical equality preserves a named value, such as `single_gpu`. Qualitative restrictions use null normalized value/unit and `qualitative`; no fake numeric bound. Unsupported mandatory enforcement blocks the affected work; a compiler does not grant tools/permissions or claim enforcement. Effective enforcement belongs to trusted binding/observations.

Metric comparison records use `comparator`, `reference` (`baseline` or `constant`) and `value`: baseline-relative thresholds are factors, constants are absolute thresholds in the stated unit. A qualitative target has null comparison, never an invented percentage. This expresses user intent, not a registered empirical measurement procedure. Missing optional metrics may remain absent.

Protected default policy supplies conservative missing parameters, currently `single_gpu` for omitted hardware. Each actual default needs policy evidence, a `system_default` field and an assumption pointing at an existing field. It does not prove hardware availability. Repetition/protocol defaults belong to Hypothesis unless explicitly requested. Defaults cannot supply unknown purpose or resolve conflicting mandatory instructions silently.

### Producer obligations (Requirements CC)

The Requirements CC owns preservation of accepted Intent. Before it returns output it re-reads the Intent against its Brief and confirms each point.

1. Every Intent constraint, target and in-scope item appears in the Brief, or appears in `unresolved_items` with a reason.
2. Every mandatory requirement is linked from at least one `acceptance_expectations` entry and one `evidence_obligations` entry.
3. Every Intent target has a `target_metrics` entry. A qualitative target keeps a null comparison and never gains an invented number.
4. Every default it applies has a `system_default` origin and an assumption with an `authority_ref` and affected-field pointers that exist. A default never supplies an unknown purpose or settles a conflict silently.
5. Derived requirements follow accepted meaning. They add no objective and choose no scientific solution.

### Deterministic host checks (Requirement)



| Check ID | Rule | Outcome on failure |
|---|---|---|
| `brief_schema` | Schema and version match. Local IDs are unique. Typed limits are valid. | Halt. No verifier call. |
| `source_identity` | `intake_ref`, `intent_ref`, every source reference and every `authority_ref` resolve to exact accepted bytes (reference resolution). Each applied default is authorized by the protected policy and points to an existing field (default authorization). | Halt. |
| `requirement_coverage` | Requirement IDs in acceptance, evidence and metric entries resolve. Every mandatory requirement is linked (requirement-link coverage). Every Intent constraint, target and in-scope item is present in the Brief or in `unresolved_items`. | Halt. |

### Verifier criteria (Brief)

The verifier sees the Requirements CC declaration and the exact `research_brief` output. Nothing else. It does not see the Intent or the defaults.

| Criterion ID | Question | Blocking |
|---|---|---|
| `declared_output_conformance` | Does the output have the artifact type, fields and shape the declaration states? | yes |
| `internal_consistency` | Do requirement, constraint, metric, acceptance and evidence entries agree, and do their ID references resolve inside the output? | yes |
| `limitations_consistency` | Are `unresolved_items` and limitations coherent with the rest of the output? | yes |
| `requirement_link_completeness` | Is every mandatory requirement linked from an acceptance expectation and an evidence obligation in the output? | yes |

Blocking unresolved items prevent acceptance.

Examples: [valid](examples/research_brief.json) · declaration: [requirements_capsule](examples/requirements_capsule.json)

## Challenge case for the Intent CC

For the worked latency request, an IR that claims the user requires a new neural retriever, cloud training or a 50% speedup adds a method, effect and target the request does not state. A span pointing at "reduce latency" does not support those additions. The Intent CC prevents this through its own self-review. Independent benchmark cases measure how often it succeeds.

## Verification cases

Fixture checks show representation and relationships. They are not measured model behavior. Real endpoint evidence and labelled challenge cases show model quality. Keep false acceptances and refusals visible. Bare `PASS`, producer readiness and valid JSON never suffice. A missing or duplicate finding, a mismatched subject or a failing mandatory check blocks release.

| Case | Expected behavior |
|---|---|
| Supported actionable request | Accepted Intent and Brief, two assessments, subnode and node decisions, observations. A test consumer reads the exact released Brief |
| Optional hardware absent | An authorized `single_gpu` assumption points to the actual Brief constraint. No observed hardware claim |
| No numeric target or method | Preserve the qualitative target and the omission. Hypothesis chooses the procedure later |
| Topic-only or unknown purpose | The Intent CC lists a blocking uncertainty and `needs_clarification`. The gate halts on readiness |
| Contradiction or invented method or target | The verifier rejects visible contradictions. Unsupported additions are a producer obligation measured by benchmark cases. No rewrite, no retry |
| Missing specified resource or unreadable directory | Explicit intake error. Rejected material is never shown as qualified |
| Malformed producer or verifier output | Deterministic halt. Bad producer output skips the verifier. A malformed assessment cannot advance |
| Missing or duplicate criterion, stale or swapped evidence | Reject even with an overall `PASS` |
| Time or call overrun, unavailable endpoint | Halt with observations. Unknown token or cost is unavailable |
| Compiler produces no artifact | A failure receipt is the check subject. Output and accepted inventories stay empty |
| Brief loses a constraint, defaults a purpose or invents a percentage | Requirements self-review and the `requirement_coverage` host check cover loss. Benchmark cases measure invented additions |
| Node and subnode mixup, cyclic dependency, parent budget exceeded | Reject binding or release. A parent does not pool child permissions |
| Failed persistence | No accepted-output publication. Keep the candidate and error when possible |
