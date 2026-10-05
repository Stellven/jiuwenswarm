---
type: payload-type
id: cc.type.poc_bundle
version: 2
status: draft
tags: [types, m1]
prd: [3.6.5]
level: detail
---

# `poc_bundle`: the benchmark-ready proof of concept · version 2

PRD: 3.6.5

The immutable four-file bundle assembled under PRD 3.6. [POC](../capabilities/poc.md) produces it and [Benchmark](../capabilities/benchmark.md) consumes it. This contract permits syntax validation only at construction; scientific execution starts at 3.7.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-poc-bundle"></a>**poc_bundle** (also: POC bundle) | The immutable four-file bundle of generated proof-of-concept code (patch, harness and requirements) assembled before any execution. Construction allows syntax validation only; Benchmark runs it later. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `files` | `list<object>` | req | checked |  | At least one. Exactly one of each of the four roles |
| `files[].role` | `enum(requirements, patch, harness, environment)` | req | checked |  | Required bundle role |
| `files[].path` | `string` | req | checked |  | Safe archive-relative path; unique and no symlink, absolute path or traversal |
| `files[].content_sha256` | `sha256` | req | checked |  | Immutable bytes in the store |
| `archive_sha256` | `sha256` | req | checked |  | POC_Artifact_Bundle.zip; contents must exactly match the four-role manifest |
| `syntax_check_ref` | `Ref(artifact)` | req | checked |  | Trusted compiler/AST check evidence; model assertion is insufficient |
| `smoke_test_passed` | `boolean` | req | checked |  | True only if both Python files passed compiler [checks](../capsule/fields.md#term-check) |
| `smoke_test_output` | `text` | opt | checked |  | Non-sensitive compiler error when false |
| `ext` | `map<string, json>` | opt | checked |  | Producer extensions; consumers ignore |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | Generated schema matches |
| `poc_contract` | deterministic | `outputs` | `both` | `cc/checks/registry/research.py:poc_contract` | cc-team | Exact four roles, safe ZIP members, content hashes, trusted syntax evidence, [frozen](../system/lifecycle.md#term-freeze) method imports and output protocol; no prohibited imports or generated measurement replacement |

## Example

```json
{
  "files": [
    {
      "role": "requirements",
      "path": "requirements.txt",
      "content_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    {
      "role": "patch",
      "path": "poc_patch.py",
      "content_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    {
      "role": "harness",
      "path": "run_benchmark.py",
      "content_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    {
      "role": "environment",
      "path": "environment.json",
      "content_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  ],
  "archive_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "syntax_check_ref": {
    "id": "syntax-1",
    "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "smoke_test_passed": true
}
```
