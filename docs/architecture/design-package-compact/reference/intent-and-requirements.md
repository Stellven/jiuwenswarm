# Intent IR and Requirements IR

**Reading level: AI reference.** [Intent design](../intent-design.md) explains behavior and rationale. Required core keys below match the exact schemas. All statements need attributable support; no sample is a fill-in prompt template.

## Intent IR

Producer: Intention CC. Consumers: deterministic checker, Intent verifier, then Requirements **only after acceptance**. [Schema](schemas/intent-ir.schema.json).

| Required field | Meaning / type | Why the consumer needs it |
|---|---|---|
| `schema_version` | Current format version | Reject incompatible structures before review |
| `request_ref` | Exact original request reference | Prevent substitution and preserve meaning |
| `interpretation` | Nullable statements `problem`, `desired_change`, `requested_result` | Identify purpose and intended output without choosing a scientific solution |
| `context` | IDs, entity name/role and source spans | Make affected entities and supplied context explicit |
| `in_scope`, `out_of_scope` | Attributed statement lists | Bound Requirements and later work |
| `constraints` | ID, text, category and source spans | Preserve limits, prohibitions, time/data/format requirements |
| `preferences` | Attributed statements | Preserve optional wishes without silently elevating them |
| `user_targets` | ID, metric, target text, source spans | Preserve explicit targets; do not invent numeric thresholds |
| `context_refs` | Permitted context/source references | Resolve relevant original material |
| `uncertainties` | ID, kind, description, affected fields, blocking flag, clarification | Distinguish missing, ambiguous and conflicting meaning |
| `readiness` | Producer's `ready` / `needs_clarification` claim and reason | Explain candidate state; independent verifier/gate still decides |

An attributed statement has `id`, `text`, `source_spans`. Each span contains `source_ref`, `start`, `end`; offsets count Unicode code points in exact source text and exclude the end. IDs are unique within the IR; references must be permitted and spans nonempty/in-bounds. Preserve original source bytes before any extraction/normalization and identify the extracted source text separately when relevant.

**Deterministic checks:** schema/version, required structure, identity/source resolution, span ranges, local IDs, actual invocation completion, pinned implementation and supported effects/limits. Do not treat them as proof of faithful or useful interpretation.

**Semantic checks:** coverage of material meaning; support for claims/paraphrases; preserved exclusions/constraints/preferences; consistent entities/scope; explicit uncertainty; enough purpose/result to define Requirements without inventing what the user wants. Optional methods/hardware/thresholds can remain absent. Not knowing the requested work is blocking. Impossible or contradictory required constraints block; uncertain scientific success is not itself an unusable research intent.

An honest `needs_clarification` artifact is structurally valid, retained candidate data. Its verifier returns a non-advancing verdict. An unsupported confident `ready` artifact must also block. The verifier does not create corrected Intent; the host routes a useful explanation to the user.

## Research Brief / Requirements IR

Producer: Requirements CC within the Intention Compiler node. Consumers: deterministic checks, Requirements verifier, node gate, then static binder/planner and research CCs **after node release**. [Critical schema](schemas/research-brief.schema.json), version `2.0.0`. The external name remains `Research_Brief.json`; Requirements IR is a descriptive alias, not a second format.

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
| `unresolved_items` | Missing/ambiguous/conflicting information and blocking disposition | Block material uncertainty instead of manufacturing requirements |
| `confirmation` | User-request or authorized-assumption basis with sources | Record permission to proceed without asynchronous approval waiting |

Requirement statements contain `id`, `text`, `origin` (`user`, `system_default`, `derived`) and source references. Local IDs are unique. Acceptance/evidence/metric requirement IDs resolve. Derived requirements follow accepted meaning; they cannot introduce a new objective or chosen scientific solution.

Quantitative constraints preserve the stated value, unit and comparison (`lt/le/eq/ge/gt`), plus compiler/run/scientific-execution scope. Categorical equality preserves a named value, such as `single_gpu`. Qualitative restrictions use null normalized value/unit and `qualitative`; no fake numeric bound. Unsupported mandatory enforcement blocks the affected work; a compiler does not grant tools/permissions or claim enforcement. Effective enforcement belongs to trusted binding/observations.

Metric comparison records use `comparator`, `reference` (`baseline` or `constant`) and `value`: baseline-relative thresholds are factors, constants are absolute thresholds in the stated unit. A qualitative target has null comparison, never an invented percentage. This expresses user intent, not a registered empirical measurement procedure. Missing optional metrics may remain absent.

Protected default policy supplies conservative missing parameters, currently `single_gpu` for omitted hardware. Each actual default needs policy evidence, a `system_default` field and an assumption pointing at an existing field. It does not prove hardware availability. Repetition/protocol defaults belong to Hypothesis unless explicitly requested. Defaults cannot supply unknown purpose or resolve conflicting mandatory instructions silently.

**Producer → deterministic checks → semantic verification:** supply attributable complete obligations; mechanically establish schema/version, IDs, source/input relationships, normalized limits and authorized-default links; independently establish preservation, coherence, permitted defaults, deliverable/evidence completeness and downstream usability. Blocking unresolved items prevent acceptance even when JSON validates. Node finalization releases the Brief only after both work boundaries and aggregate obligations pass.

## Unsupported confident interpretation

For the worked latency request, an IR claiming that the user requires a new neural retriever, cloud training, or a 50% speedup adds unsupported method, effect or target information. Even with valid fields and source-span bounds, its semantic fidelity finding must fail and the gate must halt. A source span pointing at “reduce latency” cannot substantiate those additions. The verifier reports the unsupported fields; it does not rewrite them into a competing solution.
