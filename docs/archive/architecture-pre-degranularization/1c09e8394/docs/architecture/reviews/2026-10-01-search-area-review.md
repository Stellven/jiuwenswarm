---
type: review
status: processed
tags: [review, search]
---

# Review, 2026-10-01: search and its gate

The area loop for PRD 3.3 ([search capsule](../m1/search-capsule.md), [search gate](../m1/search-gate.md), [`op.local_search`](../m1/op-local-search.md), [`op.scholarly_search`](../m1/op-scholarly-search.md), [`idea_set`](../types/idea-set.md), [`search_hits`](../types/search-hits.md)).

## Canary

- **Seam** `research.compile_brief` to `research.search_ideas` (`canary --producer/--consumer`): **agree**.
- **Blind derivation** of `research.search_ideas` with its own page hidden: every interface fact agreed (kind, ports, types, pins, effect class, network). Only the capsule's own check ids and failure code differed, which only its own page can define. Its guesses exposed three gaps, all fixed:
  - network is not inherited from operators ([runner](../capsule/runner.md#nested-calls-and-the-broker));
  - `effects_cover_dependencies` is now stated in [policy](../schemas/policy.md);
  - a multi-file tool names its entry in `ext.cc.entry` ([toolchain](../capsule/toolchain.md#the-capsule-folder)).

## Opus review: verdict "after fixes"

Every code claim was re-checked at deepsearch `ff243bc` before it was applied.

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | The gate bundle carried the whole intake, with no size limit | major | fixed: run-plan `judge_inputs` (a port, or one field of it), and policy `runner.max_bundle_bytes`; an oversized bundle gives `blocked`, never a runtime failure |
| 2 | arXiv full-text fetching was on: it scrapes pages (3.3.2 excludes this) and can pass the time budget | major | fixed: the adapter builds both wrappers with `fetch_full_text=False` |
| 3 | Semantic Scholar's no-abstract fallback is not a verbatim passage | major | fixed: such rows are dropped; whitespace collapsing is stated |
| 4 | arXiv HTTP errors and slow calls were blamed on the capsule | major | fixed: every error and timeout becomes `ExternalUnavailable`; arXiv spacing is kept across processes; the search budget is 900 s |
| 5 | A partial outage was invisible, and the wrong party was blamed | major | fixed: `cc.call` returns the nested `issues`; `EXTERNAL_UNAVAILABLE` is allowed as an issue code; an empty search caused by an outage raises `ExternalUnavailable`, not `NO_SOURCES_FOUND` |
| 6 | The intake was re-sent on every nested call, and was required even for external search | major | fixed: the operator is split into `op.local_search` (`pure`, no network) and `op.scholarly_search` (`read_only`, egress); `cc.input_ref` passes the intake by reference; policy `runner.max_intake_text_bytes` keeps an intake within a frame |
| 7 | The dependency claim was wrong | major | fixed in integration and open issue 33 |
| 8 | `within_inline_limit` could fail valid runs | major | fixed: a deterministic fit step drops the lowest-ranked local passages and records the drop |
| 9 | The local keyword algorithm was too loose | major | fixed: specified exactly on `op.local_search` |
| 10 | The replay key was incomplete | minor | fixed: one recording per service request, keyed by service, query and `max_results` |
| 11 | `EXTERNAL_UNAVAILABLE` was missing in two runner definitions | minor | fixed |
| 12 | arXiv ids and the examples did not match the wrapper | minor | fixed: version suffixes stripped; examples corrected |
| 13 | Top-K written three times; operator checks run only at admission | minor | fixed: `TOP_K` is named once; the operator pages say their checks run at admission |
