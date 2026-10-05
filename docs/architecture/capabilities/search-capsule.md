---
id: cap.search-capsule
type: capability
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, op-local-search.md, op-scholarly-search.md, ../capsule/runner.md]
provides: [research.search_ideas]
consumes: [cc.type.research_brief, cc.type.intake, cc.type.idea_set, op.local_search, op.scholarly_search]
depends_on: [../types/idea-set.md, ../types/research-brief.md, op-local-search.md, op-scholarly-search.md, README.md, search-gate.md]
tags: [m1, capsule]
level: detail
prd: [3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.5, 3.3.6]
---

The work capsule for PRD 3.3 Search & Ideation, the PRD's `search_capsule`.

# `search_capsule`: `research.search_ideas`

PRD: 3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.5, 3.3.6

> Answers: How does the search capsule turn a Research Brief into one to three cited candidate ideas?

## What it does

From the [Research Brief](../types/research-brief.md#term-research-brief), it forms keyword queries, searches the user's documents and the academic literature, keeps the verbatim passages that matched, and writes 1 to 3 candidate ideas, each citing the passages it rests on.

| PRD step | What the [capsule](../capsule/capsule.md#term-capability-capsule) does |
|---|---|
| 3.3.1 Search strategy | one model [turn](../system/model-bridge.md#term-model-turn) turns the Brief into 2 to 5 keyword queries |
| 3.3.2 Hybrid retrieval | for each query, one [`op.local_search`](op-local-search.md) call over the intake's documents and one [`op.scholarly_search`](op-scholarly-search.md) call over arXiv and Semantic Scholar, each with `top_k` = `TOP_K` = 5, the one place this number is set. One query at a time, in order |
| 3.3.3 Signal extraction | keeps the verbatim passages the [operator](README.md#term-operator) returned |
| 3.3.4 Signal organization | groups them by query into `groups`, in query order |
| 3.3.5 Idea generation | one model turn writes 1 to 3 ideas from the grouped passages, each citing chunk ids |
| 3.3.6 Compilation | returns the [`idea_set`](../types/idea-set.md), the PRD's `Candidate_Set.json` |

**Why a `tool`, not a `skill`.** PRD 3.3.2 asks for a "strict programmatic Top-K", and 3.3.3 and 3.3.4 are extraction and grouping. Only code can promise those. The two model [steps](../system/nodes.md#term-step) are `cc.model` calls from the code, with their prompts in body files, so [RSI](../rsi.md#term-rsi) can tune the prompts without touching the code.

## Where it sits

[Planned node](../system/nodes.md#term-planned-node) in the research chain template (see [capabilities](README.md)). Work capsule `research.search_ideas`; its [Gate](../verification.md#term-gate) is the profile [`research.accept_ideas.v1`](search-gate.md) of the shared `research.verifier`. Inputs `research_brief` (from the requirement CC) and `intake`; the planner binds them.

## Gate

- **Gate:** shared `research.verifier`, profile [`research.accept_ideas.v1`](search-gate.md), following [the gate capsule pattern](../capsule/gate-capsules.md).
- **[Tier 1](../verification.md#term-tier-1):** this capsule's deterministic [checks](../capsule/fields.md#term-check) below, and the `idea_set` type's checks. Together they cover PRD 3.3.6's "schema and token limits".
- **[Tier 2](../verification.md#term-tier-2):** the step checks `ideas_grounded` and `ideas_answer_brief`, defined in the profile [`research.accept_ideas.v1`](search-gate.md).

## Declaration (`capsule.json`)

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "research.search_ideas",
    "kind": "tool",
    "body": [
      {"path": "search_ideas.py", "sha256": "<author kit>"},
      {"path": "prompts/queries.md", "sha256": "<author kit>"},
      {"path": "prompts/ideas.md", "sha256": "<author kit>"}
    ],
    "summary": "From a Research Brief and the request's documents, form keyword queries, search the documents and the academic literature, and propose one to three candidate ideas, each citing the verbatim passages it rests on."
  },
  "ext": {"cc": {"entry": "search_ideas.py:search_ideas"}},
  "ports": {
    "inputs": [
      {"name": "research_brief", "type": "research_brief", "required": true, "description": "The Brief: objective, scope and constraints steer the queries."},
      {"name": "intake", "type": "intake", "required": true, "description": "The request and its documents, searched as the local scope."}
    ],
    "outputs": [
      {"name": "idea_set", "type": "idea_set", "check_id": "chunks_grounded", "description": "The queries, the evidence by query, and the candidate ideas."}
    ]
  },
  "needs": {
    "when": [],
    "external": [
      {"ref": "op.local_search", "decl_hash": "<admitted>", "purpose": "run each query over the request's documents"},
      {"ref": "op.scholarly_search", "decl_hash": "<admitted>", "purpose": "run each query against arXiv and Semantic Scholar"}
    ],
    "network": "none",
    "human_interaction": "none",
    "resources": {"timeout_s": 900}
  },
  "changes": {"effect_class": "read_only", "effects": [], "state_kind": "reads_external"},
  "guarantees": {
    "checks": [
      {"id": "chunks_grounded", "anchor": "deterministic", "target": "ports.outputs.idea_set",
       "over": "inputs_and_outputs", "applies_at": "both",
       "runner": {"ref": "checks/search_checks.py:chunks_grounded", "sha256": "<author kit>"},
       "description": "Every local chunk's source_id is an intake document_id and its text appears verbatim in that document; every external chunk's source has an http or https locator.",
       "author": "cc-team"},
      {"id": "ideas_one_to_three", "anchor": "deterministic", "target": "ports.outputs.idea_set",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/search_checks.py:ideas_one_to_three", "sha256": "<author kit>"},
       "description": "There are one to three ideas, and two to five queries.",
       "author": "cc-team"},
      {"id": "top_k_respected", "anchor": "deterministic", "target": "ports.outputs.idea_set",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/search_checks.py:top_k_respected", "sha256": "<author kit>"},
       "description": "Each query's group has chunks from at most TOP_K (5) external sources and at most TOP_K local documents.",
       "author": "cc-team"},
      {"id": "within_inline_limit", "anchor": "deterministic", "target": "ports.outputs.idea_set",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/search_checks.py:within_inline_limit", "sha256": "<author kit>"},
       "description": "The value's canonical JSON is at most the policy's runner.max_inline_file_bytes, so the next model step can read it whole.",
       "author": "cc-team"},
      {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.idea_set",
       "over": "inputs_and_outputs", "applies_at": "admission",
       "runner": {"ref": "checks/search_checks.py:matches_reference", "sha256": "<author kit>"},
       "description": "On a test case, the queries and every idea's cited_chunk_ids equal the expected ones.",
       "author": "cc-team"}
    ],
    "failure_modes": [
      {"reason_code": "NO_SOURCES_FOUND", "when": "Every query found no local passage and no external source.", "retriable": false}
    ]
  },
  "evolution": {"rsi": "none"}
}
```

**Why these choices:**

- **`read_only`, `reads_external`:** it changes nothing, and `op.scholarly_search` reads public services. Rule `effects_cover_dependencies` (proposed) holds: `read_only` covers `pure` and `read_only`.
- **`timeout_s: 900`:** up to 5 queries, each one local call (seconds) and one scholarly call (up to 120 s), plus two model turns. Within the policy cap of 1800.
- **`network: none`** for the capsule itself: only `op.scholarly_search` reaches the network.
- **`within_inline_limit`** reads its limit from `context.runner_limits` ([checks](../schemas/checks.md#calling-convention)), so the check never copies a policy value.
- **M1 RSI cannot mutate this capability.** The [frozen](../system/lifecycle.md#term-freeze) whitelist permits only the isolated Screening targets. Manual prompt revisions use ordinary admission and versioning; the referee, checks and operators remain independently governed.

## How it works

API-level, so the code fits the checks:

1. `cc.model` with `prompts/queries.md` and the Brief as JSON. The reply is `{"queries": ["...", ...]}`, 2 to 5 strings. Queries get ids `Q1`, `Q2`, ... in order.
2. For each query, in order:
   - `cc.call("op.local_search", query=..., top_k=TOP_K, intake=cc.input_ref("intake"))`: the intake is passed by reference, never re-sent;
   - `cc.call("op.scholarly_search", query=..., top_k=TOP_K)`.

   Every `EXTERNAL_UNAVAILABLE` issue on a result is carried forward with `cc.issue("idea_set", "EXTERNAL_UNAVAILABLE", ...)`.
3. `sources` is every hit's source, once each, in first-seen order. `groups` has one entry per query, its chunks in hit order, with ids `<query_id>-C<n>`.
4. **Fit.** If the `idea_set` so far (without ideas) is over `runner.max_inline_file_bytes` minus 20,000, drop the lowest-ranked local passages, last query first, until it fits. Then add `cc.issue("idea_set", "INPUT_INCOMPLETE", "<n> passages dropped to fit")`.
5. `cc.model` with `prompts/ideas.md` and the groups as JSON. The reply is `{"ideas": [...]}` in the `idea_set` idea shape; a cited id that is not a chunk is a reply error.
6. Return the `idea_set`.

**When something fails:**
- A model reply that does not parse is a capsule error.
- A nested call that ends with a runtime-owned reason (`EXTERNAL_UNAVAILABLE`, `TIMEOUT`) is re-raised unchanged ([runner](../capsule/runner-broker.md#nested-calls-and-the-broker)), so the step [halts](../system/lifecycle.md#term-halt) as `ENVIRONMENT_BLOCKED`. Recovery reads committed evidence; a new execution requires explicit human restart and a newly reserved attempt under [lifecycle](../system/lifecycle.md).
- If every group is empty and some service was unavailable, the capsule raises `cc.ExternalUnavailable`: the outside failure is the cause.
- If every group is empty and every service answered, it ends with its declared failure `NO_SOURCES_FOUND`. At M1 the reason is `CAPSULE_ERROR`, with the code in `ext.runner.failure_code`, and the run halts as `ESCALATE_TO_HUMAN`: there is nothing to build on.

## Checks

The checks are the `checks` array in the [Declaration](../capsule/fields.md#term-declaration) above. The Tier 2 step checks are in the [search gate](search-gate.md).

## Existing code it touches

None directly: its operators do ([`op.local_search`](op-local-search.md), [`op.scholarly_search`](op-scholarly-search.md)). Its model turns go through M05 and `cc.adapters.codex`.

## Tests

Five [test cases](../schemas/checks.md#term-test-case), one per `admission` or `both` check (rule `one_test_per_admission_check`), built from two requirement-capsule [fixtures](../system/test-surfaces.md#term-fixture). Each carries:
- `model_replies`: the two turns;
- `fixtures`: the deepsearch replay files for every scholarly request ([integration](../system/integration.md#deepsearch-scholarly-search)).

## Open

- `NO_SOURCES_FOUND` halts the run. A gentler path (rewrite the queries and search again) is PRD 3.3.1's blacklisted dynamic reformulation, so it waits for a later milestone.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.search-capsule.AC-01 | PRD 3.3.1 | The strategy turn returns 2 to 5 queries with ids Q1.. in order; any other count is a capsule error. | BLOCK |
| cap.search-capsule.AC-02 | PRD 3.3.2 | Each query makes exactly one op.local_search call and one op.scholarly_search call with top_k 5, in query order. | BLOCK |
| cap.search-capsule.AC-03 | PRD 3.3.5 | The [idea_set](../types/idea-set.md#term-idea-set) holds 1 to 3 ideas; every cited chunk id resolves to a retained chunk, and an unknown id is a reply error. | BLOCK |
| cap.search-capsule.AC-04 | PRD 3.3.4 | Groups follow query order; sources appear once each in first-seen order. | BLOCK |
| cap.search-capsule.AC-05 | N_node | Over the inline size limit minus 20,000 bytes, lowest-ranked local passages are dropped (last query first) and one INPUT_INCOMPLETE issue states the count dropped. | BLOCK |
| cap.search-capsule.AC-06 | N_node | All groups empty and every service answered ends with NO_SOURCES_FOUND and a human-escalation halt; all empty with a service down ends with ExternalUnavailable. | BOUNDARY |
| cap.search-capsule.AC-07 | N_node | A nested call ending with EXTERNAL_UNAVAILABLE or TIMEOUT is re-raised unchanged and the step halts as ENVIRONMENT_BLOCKED. | BOUNDARY |
| cap.search-capsule.AC-08 | US-07, G_node | A recorded idea set that claims more than its chunk says fails ideas_grounded and no successor node starts. | SYSTEM |
