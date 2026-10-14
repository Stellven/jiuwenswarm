# Search CC (`research.search`)

**Reading level: AI reference.**

**Summary for reviewers.**
- Search takes the accepted Research Brief and a plan-bound `search_scope`. The scope sets bounds only. Search writes its own keyword queries inside those bounds (PRD 3.3.1) and runs them over the permitted connectors only.
- It captures exact source excerpts and proposes 1 to 3 ideas. Every idea cites at least one captured excerpt.
- The host checks that each excerpt really is in the captured source bytes. The verifier only judges the quality of the ideas as written.
- The candidate set records the queries Search actually ran. An external connector that is down is recorded as `unavailable`. Search never invents a hit to cover for it.
- Old names "Search and Ideation", "discovery" and "ideation" all mean this CC. The CC name is `research.search`.

## Purpose and place in the run

Search is the first research stage after the Brief is accepted. The static template always runs it. The Planner may not skip it. The protected binder builds the `search_scope` from the run configuration, the resource inventory and, in planned mode, the Planner's optional `topic_hints`, then freezes it into the run plan. The scope gives bounds. It gives no queries. Search writes its own queries from the Brief, runs them in one linear pass and does not reformulate or loop (PRD 3.3.1 blacklist). It feeds [Screening](screening.md).

## Declaration

Declaration example: [search_capsule.json](../examples/search_capsule.json). It validates against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name and kind | `research.search`, kind `agent` |
| Inputs | `brief` (`research_brief`), `search_scope` (`search_scope`) |
| Output | `candidate_set` (`candidate-set:field-contract:2`) |
| Needs | Allowlisted egress to `export.arxiv.org` and `api.semanticscholar.org`, the `deepsearch` operator, read access to the local document buffer, the model bridge |
| Effect class | `read_only`. The only effects are model calls and query text that Search wrote, sent to allowlisted hosts |
| Budget | 300 s wall time, 2 model invocations, 20 tool calls, all hard |
| Checks | The bundle in the deterministic check table below, then the semantic criteria below |

## Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `brief` | `research_brief` | Requirement CC | yes | Source of the objective, mandatory requirements and constraints that shape ideas |
| `search_scope` | `search_scope` | Protected binder (plan-bound, `run_input_key` `search_scope`) | yes | The bounds: permitted connectors, local documents, query and hit limits, optional topic hints |

### `search_scope` field contract

`search-scope:field-contract:1`. It holds bounds only. It holds no query text. The protected binder builds it and freezes it into the run plan. The Planner contributes only `topic_hints` through its proposal. Search may not change the scope.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | `1.0.0` | Format version |
| `id` | `string` | yes | `search_scope` | Record identity |
| `brief_ref` | `Ref` | yes | Must equal the accepted Brief | The Brief this scope serves |
| `connectors` | `string[]` | yes | 1 to 3 items from `local_documents`, `arxiv`, `semantic_scholar`. No duplicates | The retrieval sources Search may use. Anything not listed is forbidden |
| `max_queries` | `integer` | yes | 1 to 8 | Most queries Search may write and run |
| `max_hits_per_query` | `integer` | yes | 1 to 5 | Most sources one external connector may contribute per query |
| `local_document_refs` | `Ref[]` | yes | 0 or more. Each must be a captured local document. Must be non-empty when `local_documents` is in `connectors` | The user's local documents Search may read |
| `topic_hints` | `string[]` | yes | 0 to 5 items. Each 3 to 100 characters. No duplicates. Empty in static mode | Optional topic phrases from the Planner. Search may use them when it writes queries. It may ignore them. They never replace the Brief |

Examples: [valid](../examples/search_scope.json)

## Output field contract

`candidate-set:field-contract:2`. Version 2 replaces version 1. It adds `scope_ref`, `connector_outcomes` and the citation fields `connector`, `query`, `title`, `char_start`, `char_end` and `excerpt_sha256`. It also tightens the idea limits. `queries` records the queries Search wrote and ran.

### `candidate_set`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | `2.0.0` | Format version |
| `id` | `string` | yes | `candidate_set` | Record identity |
| `brief_ref` | `Ref` | yes | Equals the `brief` input | The Brief this set serves |
| `scope_ref` | `Ref` | yes | Equals the `search_scope` input | The scope whose bounds Search ran under |
| `queries` | `string[]` | yes | 1 to `search_scope.max_queries` items. Each 3 to 200 characters. No duplicates | The queries Search itself wrote and ran, in run order. Every citation `query` is one of them |
| `connector_outcomes` | `ConnectorOutcome[]` | yes | Exactly one row per connector in the scope | What happened to each permitted connector, including failures |
| `citations` | `Citation[]` | yes | 1 or more. `id` values unique | Exact excerpts captured from sources |
| `ideas` | `Idea[]` | yes | 1 to 3 items. `idea_id` values unique | The grounded candidate ideas |

### `ConnectorOutcome`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `connector` | `string` | yes | One of `local_documents`, `arxiv`, `semantic_scholar` | The connector this row describes |
| `status` | `string` | yes | `used` or `unavailable` | `used` means it answered. `unavailable` means it could not be reached or returned an error |
| `reason` | `string` | yes | 1 to 200 characters | Plain statement of what happened. Never empty |
| `citations_captured` | `integer` | yes | 0 or more. Equals the count of citations with this `connector`. Must be 0 when `status` is `unavailable` | How many citations came from this connector |

### `Citation`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `id` | `string` | yes | Pattern `^citation:[a-z0-9_]+$` | Stable citation ID that ideas point to |
| `source_ref` | `Ref` | yes | Must name a source file in the run's capture store. The `sha256` must match those bytes | The exact captured source bytes the excerpt comes from |
| `connector` | `string` | yes | One of `local_documents`, `arxiv`, `semantic_scholar`. Must have `status` `used` | Which connector produced the source |
| `query` | `string` | yes | Must be one of `queries` | The query, written by Search, that found this source |
| `title` | `string` | yes | 1 to 300 characters | Title of the source, or the file name for a local document |
| `locator` | `string` | yes | 1 to 300 characters | Human-readable origin and position, for example a URL or file name plus a sentence number |
| `char_start` | `integer` | yes | 0 or more, less than `char_end` | Start of the excerpt in the decoded source text. Counted in Unicode code points. The source is decoded as UTF-8 with line endings unchanged |
| `char_end` | `integer` | yes | At most the decoded source length | End of the excerpt. Exclusive |
| `excerpt` | `string` | yes | 1 to 2000 characters. Equals the source text from `char_start` to `char_end` exactly | The verbatim passage. No paraphrase, no trimming, no added ellipsis |
| `excerpt_sha256` | `sha256` | yes | SHA-256 of the UTF-8 bytes of `excerpt` | Lets a reader detect any later change to the excerpt |

### `Idea`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `idea_id` | `string` | yes | Pattern `^idea:[0-9]{3}$`. Unique in the set | Immutable ID. Later stages and tie-breaking use it |
| `title` | `string` | yes | 1 to 120 characters | Short readable name |
| `summary` | `string` | yes | 1 to 600 characters | The proposed mechanism in plain words. It says what to change and why it may help |
| `citation_ids` | `string[]` | yes | 1 or more. Each must be a `citations[].id` in this set | The evidence behind the idea. An idea with none is invalid |
| `assumptions` | `string[]` | yes | 1 or more items | Premises the idea needs that nothing has proved |
| `risks` | `string[]` | yes | 1 or more items | Known ways the idea could fail |

Examples: [valid](../examples/candidate_set.json) · rejected by `idea_count`: [candidate_set_invalid_four_ideas](../examples/candidate_set_invalid_four_ideas.json) · rejected by `idea_citations_resolve`: [candidate_set_invalid_uncited_idea](../examples/candidate_set_invalid_uncited_idea.json)

## Producer obligations

Search must:

1. Write its own keyword queries from the Brief, using the scope's `topic_hints` only as optional help. Write at most `max_queries` queries. Run each one once, in order, and record exactly those queries in `queries`. Use only the scope's connectors. Never add a connector.
2. Respect `max_hits_per_query` for each external connector.
3. Capture each source to the run's capture store before it quotes it. Quote only from captured bytes.
4. Copy excerpts verbatim and record `char_start`, `char_end` and `excerpt_sha256` for each.
5. Record one `connector_outcomes` row for every permitted connector. Record `unavailable` with a reason when a connector fails. Never fill the gap with remembered or invented sources.
6. Propose 1 to 3 ideas. Each idea uses only evidence in `citations`.
7. Run its own self-review before output. Re-read each idea and confirm it cites at least one citation. Re-read each citation and confirm its excerpt, offsets and hash. Confirm the ideas are not paraphrases of each other.

Search must not run a second search round, rewrite a query after seeing results, self-reflect on coverage, browse the open web or call a connector outside the scope.

## Deterministic check bundle

The host runs these before the verifier. The binder assigns them. The Planner may suggest more but may not drop or weaken any.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `output_structure` | Output parses and matches the field tables, including enums and lengths | reject |
| `brief_binding` | `brief_ref` equals the accepted Brief | reject |
| `scope_binding` | `scope_ref` equals the bound scope | reject |
| `queries_within_bounds` | `queries` has 1 to `max_queries` items, each 3 to 200 characters, no duplicates | reject |
| `connector_outcomes` | One row per scope connector, none outside the scope. `citations_captured` matches the citation count. `unavailable` rows have no citations | reject |
| `idea_count` | `ideas` has 1 to 3 items | reject |
| `idea_ids_unique` | No two ideas share an `idea_id`. No two citations share an `id` | reject |
| `idea_citations_resolve` | Every idea has at least one `citation_ids` entry and every entry names a citation in the set | reject |
| `citation_source_resolves` | Every `source_ref` exists in the capture store and its bytes hash to `sha256`. Local sources are among `local_document_refs` | reject |
| `excerpt_matches_source` | The decoded source text from `char_start` to `char_end` equals `excerpt` | reject |
| `excerpt_hash` | `excerpt_sha256` equals the SHA-256 of the excerpt bytes | reject |
| `citation_query_ran` | Each citation `query` is in `queries` and its `connector` has status `used` | reject |
| `hit_limit` | For each external connector and query, distinct sources do not exceed `max_hits_per_query` | reject |

Excerpt matching reads captured source bytes from the run store. The verifier never does this.

## Verifier criteria

The verifier sees only the pinned declaration and the exact `candidate_set`. It cannot open sources. It judges only how the ideas read. Whether the ideas are supported by their excerpts is not established by the verifier or by these checks.

| Criterion ID | Question | Blocking |
|---|---|---|
| `idea_states_mechanism` | Does each idea summary state a concrete change and a reason it may help, rather than only a topic? | yes |
| `ideas_are_distinct` | Do the ideas differ in mechanism, rather than restating one idea? | yes |
| `assumptions_and_risks_specific` | Are the assumptions and risks specific to the idea, rather than generic statements? | no |

## Gate rule

The gate accepts when every deterministic check passes and every blocking criterion passes. It rejects on any failed check or blocking criterion. It halts when a check cannot run, for example when the capture store is unreadable.

## Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| One or more connectors `unavailable`, at least one citation captured | Accept with the outcomes recorded. Screening proceeds on the evidence found | The candidate set and outcome rows |
| No citation captured from any connector | Halt with reason `no_evidence`. No candidate set is committed | Connector outcomes and run records |
| Any deterministic check fails | Reject. No retry loop | The rejected candidate set and check results |
| Search budget exhausted | Halt | Partial records |

## Examples

| File | Role | Rejected by |
|---|---|---|
| [search_scope.json](../examples/search_scope.json) | valid input | none |
| [candidate_set.json](../examples/candidate_set.json) | valid output. Two ideas. Two queries Search wrote. Two connectors unavailable | none |
| [candidate_set_invalid_four_ideas.json](../examples/candidate_set_invalid_four_ideas.json) | four ideas | `idea_count` |
| [candidate_set_invalid_uncited_idea.json](../examples/candidate_set_invalid_uncited_idea.json) | idea with no citation | `idea_citations_resolve` |
| [search_capsule.json](../examples/search_capsule.json) | declaration | none |

## Future seams

- A later Router may choose the model Search uses. The declaration names no model.
- Dynamic query reformulation and coverage loops (PRD 3.3 blacklist) can come later as new CC versions. The `queries` and `connector_outcomes` fields already record what a loop would need.
- New connectors need a new enum value and a new capsule version. The scope already lists connectors explicitly.
- Planner search planning can send richer `topic_hints` without changing this contract. Queries stay Search's own.
