---
type: schema
id: cc.candidate.v1
status: proposed
tags: [schema]
---

# Candidate · `cc.candidate.v1`

A submission to admission: a Declaration, the files it points at, its tests, how it was built and where it came from. It is the only way into the library, for authors, RSI and importers alike. The submitter writes it; admission only reads it (INV-3).

**Rules:** INV-3, INV-10.

## Fields

Extends [common](common.md), with `scope.candidate_id` equal to its own `id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `submitted_by` | `object` | req | checked |  | Who answers for the submission |
| `submitted_by.kind` | `reg(submitter_kind)` | req | checked |  | `author`, `rsi` or `importer` |
| `submitted_by.id` | `string` | req | checked |  | An author's handle, an RSI run id, or an importer's name. Example: `author-17` |
| `declaration` | `json` | req | checked |  | The [Declaration](declaration.md) being submitted, in full |
| `files` | `list<object>` | req | checked |  | The code the Declaration's `carrier` or `body` names. Admission hashes each file again and refuses a mismatch |
| `files[].path` | `string` | req | checked |  | Relative to the capsule root. Example: `pdf_text.py` |
| `files[].sha256` | `sha256` | req | checked |  | The file's hash |
| `files[].content_ref` | `uri` | req | checked |  | Where admission can fetch the bytes |
| `tests` | `list<object>` | req | checked |  | The submitter's test cases, inline; at least one. Admission stores each as a [test case](checks.md) and groups them into one visible suite. The policy also requires one per `admission` or `both` check |
| `tests[].check_id` | `id` | req | checked |  | The check the case exercises. Example: `text_not_empty` |
| `tests[].inputs` | `map<string, json>` | req | checked |  | Input port name to value. Admission stores each value as one Artifact. A `file` or `path` value is given as a URI, which admission fetches. Example: `{"pdf": "https://example.org/sample.pdf"}` |
| `tests[].expected` | `json` | req | checked |  | The expected output, or a judged check's rubric. Example: `{"text": {"min_chars": 1}}` |
| `tests[].fixtures` | `list<uri>` | opt | checked |  | Outside state the case needs, fetched and stored by admission as Artifacts |
| `tests[].negative_control` | `boolean` | opt | unchecked | certification | `true` when the case must fail |
| `requested_level` | `enum(provisional, certified)` | opt | unchecked | certification | The level asked for. Default `provisional` |
| `builder_evidence` | `object` | opt | unchecked | RSI | How it was built. **Kept, never counted as a passed check** (INV-10) |
| `builder_evidence.generating_model` | `string` | opt | unchecked | RSI | The model that wrote it. Example: `qwen3-32b` |
| `builder_evidence.prompt_ref` | `uri` | opt | unchecked | RSI | The prompt that produced it |
| `builder_evidence.trajectory_ref` | `id` | opt | unchecked | RSI | An agent-core trajectory id: what the builder did |
| `builder_evidence.builder_gate` | `json` | opt | unchecked | RSI | The builder's own test result, e.g. RSI's score and baseline. A label only |
| `test_aids` | `list<Ref(artifact)>` | opt | unchecked | RSI | Example inputs and fixtures for testers and RSI. Never evidence |
| `source` | `object` | opt | unchecked | importer, store | Provenance, for imports: where the capability came from |
| `source.system` | `string` | req | unchecked | importer, store | The system it came from. Example: `skillhub` |
| `source.uri` | `uri` | req | unchecked | importer, store | Where it was fetched. Example: `https://github.com/org/pdf-tools` |
| `source.name` | `string` | req | unchecked | importer, store | Its name upstream. Example: `pdf-tools` |
| `source.version` | `string` | req | unchecked | importer, store | Its version upstream, a tag or commit. Example: `v3.1.0` |
| `source.publisher` | `string` | opt | unchecked | importer, store | Who published it upstream. Example: `org` |
| `source.attestation` | `object` | opt | unchecked | store | A signature over the capsule: `{kind, uri, subject}`, where `subject` is the `decl_hash` signed. Admission refuses it when `subject` differs from the computed `decl_hash` (`HASH_MISMATCH`). Example: `{"kind": "sigstore", "uri": "...", "subject": "3f9a..."}` |

## Elsewhere

At least one test, one test per `admission` or `both` check, and what each level requires: policy `rules`, `levels`. The epoch admission uses is not named here (see Known gaps in [Schemas](schemas.md)).

## Reuse

- `EngineReport.artifact_index`, `ArtifactRef` (agent-core `rsi/schema.py:152-172`): the RSI submitter maps each `ArtifactRef` into `files`, hashing on the way in; RSI's score goes into `builder_gate`.
- `RsiChange` (`rsi/schema.py:86`): as is, in the Candidate's `ext.rsi`.
- skillhub asset versions (`plugins_market/models/market_assets.py:100`): not reused; a mutable database row.
