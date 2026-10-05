---
type: payload-type
id: cc.type.intake
version: 2
status: draft
tags: [types, m1]
---

> **Draft recheck.** Version 2 adds separately bound project and validation resources from full PRD 3.1.2. The downstream resource contract is reviewed together with launcher, Search, Hypothesis and Builder.

# `intake`: the Qualified Intake Package · version 2

The user's request and the text of their reference documents, as one value. It is PRD 3.1.5's "Qualified Intake Package": "the combined prompt and extracted document text as a single in-memory dictionary". Every M1 run starts from exactly one.

**Made by** the M01 launcher, which is control code. It calls the runner's `record_input` with `origin: human` ([runner](../capsule/runner.md#values-how-each-port-type-travels)), so the value is stored as an Artifact like any other. **Read by** the `intent` and `requirement` steps ([M1 pipeline](../m1/pipeline.md)).

**It replaces three earlier shapes.** The parked `raw_intent`, the M1 architecture's `run_request` and `documents`, and the requirement page's assumed `{prompt, documents}` all described this one value. They are retired in its favour.

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `prompt` | `text` | req | checked |  | The request exactly as the user typed it, unchanged (PRD 3.1.1). Not blank: the launcher halts before making an `intake` when it is (3.1.5). Every `source_spans` range and every `evidence` quote with `evidence_source_id: prompt` points into this string |
| `channel` | `enum(cli, web)` | req | checked |  | Where the prompt came from: the CLI `--topic` argument or the web UI prompt box (3.1.1). Other channels are excluded from M1 |
| `resources` | `list<object>` | req | checked |  | Separately bound reference documents, project assets and validation data. May be empty at raw qualification; scientific resource readiness is checked before a blueprint passes |
| `resources[].resource_id` | `id` | req | checked |  | Unique intake-local identity; downstream references use it instead of inventing a dataset document_id |
| `resources[].kind` | `enum(reference_document, project_asset, validation_data)` | req | checked |  | PRD 3.1.2 resource classification |
| `resources[].source` | `enum(supplied, preinstalled)` | req | checked |  | Supplied local input or explicitly configured, already installed local resource; no cloning/downloading |
| `resources[].path` | `string` | req | checked |  | Authorized workspace-relative path; configured external preinstalled roots are provisioned as bound workspace resources before qualification |
| `resources[].label` | `text` | req | checked |  | Human-readable resource/model/dataset name; does not prove experimental suitability |
| `documents` | `list<object>` | req | checked |  | One entry per ingested file, in path order. May be empty |
| `documents[].document_id` | `id` | req | checked |  | Unique within the intake: `doc-1`, `doc-2` and so on, in list order. Quotes from this document cite it as their `evidence_source_id` |
| `documents[].path` | `string` | req | checked |  | The file's path relative to the workspace, with forward slashes. It must name a reference_document resource. Project assets and datasets never enter this text buffer (3.1.2) |
| `documents[].format` | `enum(txt, md, pdf)` | req | checked |  | The file's extension, and so how its text was extracted (3.1.2) |
| `documents[].size_bytes` | `integer` | req | checked |  | The file's size on disk, at most the launcher's limit of 50 MB (3.1.4). The documents' extracted text together stays under policy `runner.max_intake_text_bytes` |
| `documents[].text` | `text` | req | checked |  | The extracted plain text, in reading order. Not blank: a file whose text extracts empty goes in `skipped` instead |
| `skipped` | `list<object>` | req | checked |  | Files in the input folder that were not ingested, so nothing is dropped silently. May be empty |
| `skipped[].path` | `string` | req | checked |  | The file's workspace-relative path |
| `skipped[].reason` | `enum(unsupported_format, too_large, unreadable, empty_text)` | req | checked |  | Why it was skipped |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them ([types](types.md#the-rules)) |

**Not in the value** (INV-5): the run it belongs to (the Artifact's `scope.run_id`, PRD 3.1.3), the ingest time (the Artifact's `at`, 3.1.4), and who made it (`origin: human`, `producer`).

## Type checks

Run by the gate on every `intake` value, and by `record_input` before storing it.

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.intake_ids_and_paths_unique.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intake.py:intake_ids_and_paths_unique` | muk | `documents[].document_id` values are unique, and no path appears twice across `documents` and `skipped` |
| `check.intake_resources_resolve.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intake.py:intake_resources_resolve` | muk | resource ids and paths are unique and safe relative paths; every extracted document names a reference_document resource; no project/data content is extracted |

## Example

```json
{
  "prompt": "Reduce the VRAM use of my model's attention by at least 30% without losing more than 1% accuracy. Don't retrain from scratch.",
  "channel": "cli",
  "resources": [
    {"resource_id": "res-doc-1", "kind": "reference_document", "source": "supplied", "path": "input/flash-attention.pdf", "label": "FlashAttention reference"},
    {"resource_id": "res-repo-1", "kind": "project_asset", "source": "supplied", "path": "input/repo", "label": "User baseline code"},
    {"resource_id": "res-data-1", "kind": "validation_data", "source": "supplied", "path": "input/datasets/validation", "label": "Validation split"}
  ],
  "documents": [
    {"document_id": "doc-1", "path": "input/flash-attention.pdf", "format": "pdf", "size_bytes": 1824311, "text": "FlashAttention: Fast and Memory-Efficient Exact Attention ..."}
  ],
  "skipped": [{"path": "input/slides.pptx", "reason": "unsupported_format"}]
}
```

## History

- Version 2: source/role/path resource bindings are introduced under issue 45. Raw intake qualification retains PRD 3.1.5's prompt/readability checks; absent baseline or validation data prevents a scientifically executable blueprint, rather than inventing an additional raw-intake rejection. The later immutable snapshot contract is owned by [storage](../system/storage.md).

- `raw_intent` (`cc.intent.raw.v1`, parked in obby) carried `attachments` as Artifact refs, `channel` with `tui`, and E2A `source_ref` ids. M1 has two channels (3.1.1) and attaches no chat files, so those are dropped. The E2A ids can return as optional fields when a chat channel feeds a run.
- The requirement page's assumed `documents: [{path, text, size_bytes}]` gains `document_id` and `format`, so evidence can name its document.
