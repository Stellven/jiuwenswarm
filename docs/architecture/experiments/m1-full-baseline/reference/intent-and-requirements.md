# Intent IR and Requirements IR

**Reading level: AI reference.** [Intent design](../intent-design.md) explains behavior and rationale. Required core keys below match the exact schemas. All statements need attributable support; no sample is a fill-in prompt template.

## Intent IR

Producer: Intent CC. Consumers: deterministic checker, Intent verifier, then Requirements **only after acceptance**. [Schema](schemas/intent-ir.schema.json).

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

Producer: Requirements CC. Consumers: Requirements checker/verifier, static binder/planner, research CCs and later checking. [Schema](schemas/research-brief.schema.json). It remains the PRD's `Research_Brief.json`, not another competing requirements format.

| Required field | Meaning / type | Consumer obligation |
|---|---|---|
| `schema_version`, `intent_ref` | Format and exact accepted interpretation | Bind the contract to accepted meaning |
| `objective` | Requirement statement | Establish what the program must achieve |
| `in_scope`, `out_of_scope` | Requirement statements | Preserve context boundaries |
| `mandatory_requirements`, `optional_preferences` | ID, text, origin, source references | Planner covers required outcomes; preferences cannot waive them |
| `constraints` | ID, text, category, origin, source references | Binder/runner apply applicable resource/effect restrictions |
| `target_metrics` | ID, metric, target text, source references | Hypothesis derives registered experimental criteria later |
| `deliverables` | ID, name, description, artifact type | Bind observable requested results to work/output coverage |
| `acceptance_expectations` | ID, covered requirement IDs, description | State user-level completion expectations |
| `evidence_obligations` | ID, covered requirement IDs, description | Establish evidence needed to substantiate completion |
| `assumptions` | ID, text, authority reference, affected fields | Show authorized defaults separately from user values |
| `unresolved_items` | Same uncertainty structure as Intent | Prevent silent completion of unusable requirements |
| `resource_refs` | Supplied/qualified resource references | Hypothesis/Builder/Benchmark use declared assets |
| `confirmation` | User-request or authorized-assumption basis and sources | Record authority without asynchronous approval waiting |

Requirement statements contain `id`, `text`, `origin` (`user`, `system_default`, `derived`) and nonempty `source_refs`. Defaults need permitted policy evidence plus a corresponding assumption. Derived requirements must follow accepted Intent; they cannot introduce a new objective, method or experimental conclusion. Acceptance/evidence requirement IDs must resolve; local IDs are unique.

**Deterministic checks:** exact schema/version, reference/type/scope checks, ID coverage, defaults with authority, expected outputs and supported limits. **Semantic checks:** preservation of accepted Intent, coherent mandatory/preference split, no unsupported widening, deliverables/acceptance/evidence completeness and usable planning obligations. Blocking unresolved items prevent acceptance even when the JSON validates.

Planner/static binder maps every mandatory requirement and deliverable to compatible work/output contracts. The protected binder adds all required checking/effect limits; a planner cannot waive them. Requirements is not a final experimental protocol. Hypothesis supplies measurement definitions, success/falsification and any pre-registered conditional classification before code or empirical execution.

## Unsupported confident interpretation

For the worked latency request, an IR claiming that the user requires a new neural retriever, cloud training, or a 50% speedup adds unsupported method, effect or target information. Even with valid fields and source-span bounds, its semantic fidelity finding must fail and the gate must halt. A source span pointing at “reduce latency” cannot substantiate those additions. The verifier reports the unsupported fields; it does not rewrite them into a competing solution.
