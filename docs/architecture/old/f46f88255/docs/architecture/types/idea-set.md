---
type: payload-type
id: cc.type.idea_set
version: 1
status: checked
tags: [types, m1]
---

> **Checked, not yet approved.** Written 2026-10-01 for the search area.

# `idea_set`: candidate ideas with their evidence · version 1

The output of Search & Ideation (PRD 3.3): the queries run, the verbatim evidence they found grouped by query, and 1 to 3 candidate ideas, each citing the evidence it rests on. It is the PRD's `Candidate_Set.json`. The name is `idea_set` because `Candidate` is already the CC record a capsule is submitted in.

**Made by** `research.search_ideas` at step `search` ([search capsule](../m1/search-capsule.md)). **Read by** the screening step (PRD 3.4), which merges near-duplicate ideas, keeps variants that rest on different sources (3.4.1), and builds idea cards with linked citations (3.4.3).

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `queries` | `list<object>` | req | checked |  | At least one. The keyword queries formed from the Brief (3.3.1) |
| `queries[].query_id` | `id` | req | checked |  | Unique within the value. Example: `Q1` |
| `queries[].text` | `text` | req | checked |  | The query as run. Example: `memory efficient attention` |
| `sources` | `list<object>` | req | checked |  | Every source any chunk comes from, once each. Copied from the operator's `search_hits` |
| `sources[].source_id` | `id` | req | checked |  | As in `search_hits`. Unique within the value |
| `sources[].kind` | `enum(local, arxiv, semantic_scholar)` | req | checked |  | Where it came from |
| `sources[].title` | `text` | req | checked |  | Its title, or the local document's path |
| `sources[].authors` | `list<string>` | req | checked |  | Its authors. Empty for a local document |
| `sources[].published` | `string` | opt | checked |  | Its publication date, as the source gives it |
| `sources[].locator` | `string` | req | checked |  | The workspace path or URL |
| `groups` | `list<object>` | req | checked |  | The evidence, grouped by the query that found it (3.3.3, 3.3.4). One entry per query, in query order |
| `groups[].query_id` | `id` | req | checked |  | The query whose passages these are |
| `groups[].chunks` | `list<object>` | req | checked |  | The verbatim passages it found. May be empty |
| `groups[].chunks[].chunk_id` | `id` | req | checked |  | Unique within the value. Example: `Q1-C2` |
| `groups[].chunks[].source_id` | `id` | req | checked |  | The source it is from |
| `groups[].chunks[].text` | `text` | req | checked |  | The passage, verbatim |
| `ideas` | `list<object>` | req | checked |  | At least one. The candidate ideas (3.3.5); the producer promises at most three |
| `ideas[].idea_id` | `id` | req | checked |  | Unique within the value. Example: `I1` |
| `ideas[].title` | `text` | req | checked |  | A short name for the idea |
| `ideas[].summary` | `text` | req | checked |  | What the idea is, in two or three sentences |
| `ideas[].mechanism` | `text` | req | checked |  | How it would work: the change it makes and why that should help (3.4.2 reads it) |
| `ideas[].cited_chunk_ids` | `list<id>` | req | checked |  | At least one. The chunks the idea rests on. A source is cited through its chunks |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.idea_set_references_resolve.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/idea_set.py:idea_set_references_resolve` | muk | ids are unique in their lists; every group's `query_id` is a query; every chunk's `source_id` is a source; every `cited_chunk_ids` entry is a chunk |

Whether a local chunk really appears in its document needs the intake, so it is a check of the producer.

## Example

```json
{
  "queries": [{"query_id": "Q1", "text": "memory efficient attention"}],
  "sources": [{"source_id": "arxiv:2205.14135", "kind": "arxiv",
               "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
               "authors": ["Tri Dao", "Daniel Y. Fu"], "published": "2022-05-27",
               "locator": "http://arxiv.org/abs/2205.14135v2"}],
  "groups": [{"query_id": "Q1", "chunks": [{"chunk_id": "Q1-C1", "source_id": "arxiv:2205.14135",
              "text": "Transformers are slow and memory-hungry on long sequences, since the time and memory complexity of self-attention are quadratic in sequence length."}]}],
  "ideas": [{"idea_id": "I1", "title": "IO-aware tiled attention",
             "summary": "Compute exact attention in tiles that stay in on-chip memory, so the full attention matrix is never stored.",
             "mechanism": "Replace the attention kernel with a tiled one that recomputes softmax statistics per tile, cutting memory from quadratic to linear in sequence length.",
             "cited_chunk_ids": ["Q1-C1"]}]
}
```
