---
type: payload-type
id: cc.type.search_hits
version: 1
status: checked
tags: [types, m1]
---

> **Checked, not yet approved.** Written 2026-10-01 for the search area.

# `search_hits`: what one search query found · version 1

The ranked sources one query found, with the verbatim passages that matched. It is the output of the operators [`op.local_search`](../m1/op-local-search.md) and [`op.scholarly_search`](../m1/op-scholarly-search.md), one value per call.

**Made by** `op.local_search` and `op.scholarly_search`. **Read by** `research.search_ideas`, through nested calls ([search capsule](../m1/search-capsule.md)). The query that produced it is the call's input, recorded in its Observation, not repeated here (INV-5).

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `hits` | `list<object>` | req | checked |  | The sources found, best first. May be empty |
| `hits[].source_id` | `id` | req | checked |  | Stable across runs for the same source: the intake `document_id` for a local document, `arxiv:<id>` without its `v<n>` version for arXiv, `s2:<paperId>` for Semantic Scholar. Example: `arxiv:2205.14135` |
| `hits[].kind` | `enum(local, arxiv, semantic_scholar)` | req | checked |  | Where the source came from |
| `hits[].title` | `text` | req | checked |  | The source's title, or the local document's path |
| `hits[].authors` | `list<string>` | req | checked |  | Its authors, as the source gives them. Empty for a local document |
| `hits[].published` | `string` | opt | checked |  | Its publication date, as the source gives it. Example: `2022-05-27` |
| `hits[].locator` | `string` | req | checked |  | Where to find it: the local document's workspace path, or the source's URL as the service gives it. Example: `http://arxiv.org/abs/2205.14135v2` |
| `hits[].chunks` | `list<text>` | req | checked |  | At least one. Verbatim passages that matched: for a local document, passages of its text; for an external source, its abstract as the connector returns it, with whitespace runs collapsed to one space |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.search_hits_sources_unique.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/search_hits.py:search_hits_sources_unique` | muk | no `source_id` appears twice |

## Example

```json
{
  "hits": [
    {"source_id": "arxiv:2205.14135", "kind": "arxiv",
     "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
     "authors": ["Tri Dao", "Daniel Y. Fu"], "published": "2022-05-27",
     "locator": "http://arxiv.org/abs/2205.14135v2",
     "chunks": ["Transformers are slow and memory-hungry on long sequences, since the time and memory complexity of self-attention are quadratic in sequence length."]}
  ]
}
```
