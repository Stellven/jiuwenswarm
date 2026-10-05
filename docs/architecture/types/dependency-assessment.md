---
type: payload-type
id: cc.type.dependency_assessment
version: 1
status: draft
tags: [types, m1, screening]
prd: [3.4.5]
level: detail
---

# `dependency_assessment`: frozen registry decision · version 1

PRD: 3.4.5

The deterministic policy result for one `dependency_requirement` under one [frozen](../system/lifecycle.md#term-freeze) dependency-registry version.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-dependency-assessment"></a>**dependency_assessment** (also: dependency assessment) | The deterministic policy result for one dependency requirement under one frozen dependency-registry version. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `requirement` | `object` | req | checked |  | Requirement that was assessed |
| `requirement.kind` | `enum(package, model, dataset)` | req | checked |  | Registry namespace |
| `requirement.identifier` | `string` | req | checked |  | Canonical registry identity |
| `requirement.version` | `string` | opt | checked |  | Requested version or revision |
| `status` | `enum(compatible, conflict, unknown)` | req | checked |  | Only `compatible` is eligible in M1 |
| `registry_entry_ref` | `EvidenceRef?` | req | checked |  | Exact policy evidence, or null for `unknown` |
| `reason` | `text` | req | checked |  | Deterministic explanation suitable for card disposition metadata |
| `registry_sha256` | `sha256` | req | checked |  | Frozen dependency-registry version |
| `ext` | `map<string, json>` | opt | checked |  | Producer-keyed extensions ignored by consumers |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | the value matches the generated schema |
| `check.dependency_assessment_consistent.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/dependencies.py:dependency_assessment_consistent` | cc-team | `compatible`/`conflict` resolves an entry; `unknown` has a null entry reference; reason and registry hash are present |

## Example

```json
{
  "requirement": {"kind": "package", "identifier": "pypi:torch", "version": "2.7.1"},
  "status": "compatible",
  "registry_entry_ref": {"evidence_type": "dependency_registry_entry", "reference": "dependency-pypi-torch-2.7.1"},
  "reason": "The exact wheel is present in the approved local wheelhouse and its license is permitted.",
  "registry_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```
