---
type: payload-type
id: cc.type.code_hits
version: 1
status: draft
tags: [types, m1]
prd: [3.3.2, 3.5.5]
level: detail
---

# `code_hits`: snapshot code locations · version 1

PRD: 3.3.2, 3.5.5

Ordered verbatim Python source locations produced by [CodeSearch](../capabilities/op-codesearch.md), consumed by Hypothesis and POC. Every path and line resolves against the authorized immutable project [snapshot](../capsule/library.md#term-library-snapshot).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-code-hits"></a>**code_hits** (also: code hits) | Ordered verbatim Python source locations produced by CodeSearch, each resolving against an authorized immutable project snapshot. Hypothesis and POC consume it. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `hits` | `list<object>` | req | checked |  | At most top_k entries, possibly empty, ordered by relevance with deterministic ties |
| `hits[].path` | `string` | req | checked |  | Safe snapshot-relative file path |
| `hits[].start_line` | `integer` | req | checked |  | Positive one-based inclusive start line |
| `hits[].end_line` | `integer` | req | checked |  | Inclusive end, at least start_line |
| `hits[].code` | `text` | req | checked |  | Exact selected source lines |
| `issues` | `list<Reason>` | req | checked |  | Explicit retrieval limitations; may be empty |
| `ext` | `map<string, json>` | opt | checked |  | Producer extensions; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | Matches generated schema |
| `code_hits_source` | deterministic | `outputs` | `both` | `cc/checks/registry/research.py:code_hits_source` | cc-team | Count/bounds/path and exact source match the authorized snapshot and query |

## Example

```json
{"hits":[{"path":"model.py","start_line":1,"end_line":2,"code":"def forward(x):\n    return x"}],"issues":[]}
```
