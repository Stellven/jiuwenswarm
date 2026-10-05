---
type: payload-type
id: cc.type.dependency_requirement
version: 1
status: draft
tags: [types, m1, screening]
prd: [3.4.5]
level: detail
---

# `dependency_requirement`: a candidate's external requirement · version 1

PRD: 3.4.5

A model, package or dataset identity that an opportunity says it needs, before policy determines whether it is available.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-dependency-requirement"></a>**dependency_requirement** (also: dependency requirement) | A model, package or dataset identity that an opportunity says it needs, before policy decides whether it is available. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `kind` | `enum(package, model, dataset)` | req | checked |  | Registry namespace |
| `identifier` | `string` | req | checked |  | Canonical registry identity, never a display name |
| `version` | `string` | opt | checked |  | Exact version or model/dataset revision when required |
| `evidence` | `text` | req | checked |  | Why the candidate requires it, grounded in the source idea or [Brief](research-brief.md#term-research-brief) |
| `ext` | `map<string, json>` | opt | checked |  | Producer-keyed extensions ignored by consumers |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | the value matches the generated schema |

## Example

```json
{
  "kind": "package",
  "identifier": "pypi:torch",
  "version": "2.7.1",
  "evidence": "The proposed implementation uses the locally bound PyTorch runtime."
}
```
