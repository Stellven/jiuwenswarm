---
type: payload-type
id: cc.type.source_text
version: 1
status: draft
tags: [types, m1, composition]
---

# `source_text`: text with a stable source and offset basis · version 1

The smallest independently composable text input for language capabilities. Ordinary `launcher.extract_text` projects it from an `intake`; a direct text launcher may record the same type without manufacturing an `intake` dependency.

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `text` | `text` | req | checked |  | Exact text consumed by the next capability; spans use Python-style zero-based, end-exclusive character offsets into this string |
| `source_ref` | `id` | req | checked |  | Stable identifier of the prompt, document or extracted resource represented by `text` |
| `source_kind` | `enum(prompt, document, resource)` | req | checked |  | What supplied the text |
| `content_sha256` | `sha256` | req | checked |  | SHA-256 of the UTF-8 text bytes, used for identity and replay rather than authenticity claims |
| `offset_basis` | `enum(unicode_codepoint)` | req | checked |  | The character-count convention; M1 always uses Unicode code points |
| `ext` | `map<string, json>` | opt | checked |  | Producer-keyed extensions ignored by consumers |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.source_text_hash.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/source_text.py:source_text_hash` | muk | `content_sha256` equals the SHA-256 of `text` encoded as UTF-8 |

## Example

```json
{
  "text": "Reduce peak VRAM by at least 30% without losing more than 1% accuracy.",
  "source_ref": "prompt",
  "source_kind": "prompt",
  "content_sha256": "d52e0efde980d3066305e9f49d37fe2e546f68a096dadf76e70efc542df9a51f",
  "offset_basis": "unicode_codepoint"
}
```

The example hash is checked by the vocabulary/example validator. If the prose changes, regenerate the hash before accepting the example.
