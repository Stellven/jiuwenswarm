---
type: payload-type
id: cc.type.resource_snapshot
version: 1
status: draft
tags: [types, m1, resource]
---

# `resource_snapshot`: immutable bound resource · version 1

A read-only repository, document, dataset or validation resource after the launcher/store has frozen its identity for one run.

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `resource_id` | `id` | req | checked |  | Run-local identity used by downstream payloads |
| `kind` | `enum(reference_document, project_asset, validation_data, method_asset)` | req | checked |  | Resource role used by downstream authorization and scientific readiness checks |
| `label` | `text` | req | checked |  | Human-readable name |
| `content_sha256` | `sha256` | req | checked |  | Hash of the canonical file or directory manifest |
| `manifest_ref` | `EvidenceRef` | req | checked |  | Immutable manifest containing paths, sizes and member hashes |
| `access` | `enum(read_only)` | req | checked |  | M1 consumers cannot change the snapshot |
| `ext` | `map<string, json>` | opt | checked |  | Producer-keyed extensions ignored by consumers |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.resource_snapshot_manifest.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/resources.py:resource_snapshot_manifest` | muk | the manifest resolves, contains only safe relative paths and hashes to `content_sha256` |

## Example

```json
{
  "resource_id": "res-data-1",
  "kind": "validation_data",
  "label": "Bound validation split",
  "content_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "manifest_ref": {"evidence_type": "artifact", "reference": "snapshot-manifest-1"},
  "access": "read_only"
}
```
