---
id: cap.delivery
type: module
level: detail
status: draft
version: 4
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [publication.publish_report, publication.manifest.v1]
consumes: [cc.type.research_report, cc.type.benchmark_payload, cc.type.poc_bundle]
depends_on: [README.md, write-report.md, research-gates.md, measurement-protocol.md]
tags: [m1, contract]
prd: [3.9.3, 3.9.4]
---

# Ordinary publication (delivery)

PRD: 3.9.3, 3.9.4

> Answers: How does the ordinary delivery module render and publish the run outputs, and how is the publication manifest checked?

## What it does

Delivery is an [ordinary module](README.md#term-ordinary-module) (`N_deliver`, B19 in [modules](../system/modules.md)), not a [capsule](../capsule/capsule.md#term-capability-capsule): no [Declaration](../capsule/fields.md#term-declaration), no [RSI](../rsi.md#term-rsi) and no [Gate](../verification.md#term-gate). It takes the run's terminal outputs, renders the report and the [POC bundle](../types/poc-bundle.md#term-poc-bundle) deterministically, copies their bytes into one directory and records what it wrote. The report text comes from [`research.write_report`](write-report.md), which produces the `research_report` value. Delivery then renders `research_report.md` from it and builds the POC zip, both without a model call.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-delivery"></a>**delivery** | The ordinary module that renders `research_report.md` and the POC zip deterministically, copies them into `outputs/<run_id>/` and records what it wrote. It runs after the report Gate releases and is neither a Gate nor a capsule. |
| <a id="term-publication-manifest"></a>**publication manifest** (also: delivery manifest) | The record of every published file with its relative path, hash, size and source reference, checked deterministically by delivery. |

## Interface

Schema: `library-rsi-v1.schema.json#deliver_request` `{run_id, terminal_output_refs[], destination_ref, request_id}`, reply `library-rsi-v1.schema.json#deliver_result` carrying the Ref of a `library-rsi-v1.schema.json#publication_manifest`. The manifest lists every published file with its relative path, `sha256`, size and the `source_ref` it came from.

| Port | Contract |
|---|---|
| call | `deliver(run_id, terminal_output_refs, destination_ref, request_id) -> publication_manifest_ref` |
| inputs | Artifact refs that already passed their Gates, chosen by the supervisor from the [run plan](../types/run-plan.md#term-run-plan) plan's terminal outputs; delivery never selects, renames by meaning or interprets them |
| render | `research_report` to `research_report.md` and the validated four-role POC files to `POC_Artifact_Bundle.zip`, deterministic and byte-stable |
| effect | writes, only the authorized `outputs/<run_id>/` directory |
| validation | the deterministic manifest check below, inside this module |

## Behavior

1. Start only after the report [Verification](../schemas/verification-record.md#term-verification) and release are committed.
2. Resolve the stored inputs and render `research_report.md` and the POC zip.
3. Write a sibling staging directory and verify every byte and manifest entry.
4. Publish atomically and recoverably under the store protocol, then commit the manifest.
5. The supervisor records completion only after the publication evidence exists.

Rules:

- Paths are relative, unique and free of parent traversal. Each manifest entry is verified against the stored bytes before the directory is exposed.
- A duplicate request id with identical bytes returns the committed manifest; different bytes return `REQUEST_CONFLICT`.
- A crash retains a recoverable staging record and never exposes an incomplete directory as completed.

In the research use, the terminal outputs are `research_report`, `poc_bundle` and `benchmark_payload` plus the authorized evidence context. The directory `outputs/<run_id>/` holds `research_report.md`, `POC_Artifact_Bundle.zip`, `empirical_results.json`, raw stdout and stderr and an evidence index pointing to preserved blueprints and Gate decisions. No partial directory is presented as completed. Native Web and TUI views and `/swarmflows` read the committed manifest and show paths; they never change conclusions or send external messages.

## Publication manifest check

Delivery is not a capsule and has no Gate, so there is no [Tier 2](../verification.md#term-tier-2) call. `publication.manifest.v1` is the list of this deterministic check, run inside the module against the `publication_manifest` shape. It is not a [verifier assessment](../types/verifier-assessment.md#term-verifier-assessment).

| Check | Meaning |
|---|---|
| content equality | every promised output file equals the stored content |
| one directory | the manifest is committed as one directory publication |
| path | the workspace path is the correct `outputs/<run_id>/` |
| no distribution | no external notification or distribution occurs |

## Failure

| Situation | Outcome | Recovery |
|---|---|---|
| `INPUT_MISSING`, `REFERENCE_INVALID`, `OUTPUT_INVALID` | retain evidence, halt final completion | fix inputs, human resume |
| `DESTINATION_DENIED`, `PUBLICATION_FAILED`, `STORE_WRITE_FAILED` | retain evidence, halt final completion, expose nothing | fix destination, human resume |
| timeout or cancellation | shared request lifecycle; no silent second effect | new request |
| same request id, changed bytes | `REQUEST_CONFLICT` | new request id |

The publisher is the sole writer of the output directory. [Data Foundation](../system/storage.md#term-data-foundation) is the home of Artifact and manifest records. Publication uses a staged directory with atomic replacement, following [Python os.replace](https://docs.python.org/3/library/os.html#os.replace); platform crash durability requires implementation validation.

## Template and complete inputs

The report template, the [StageContext](write-report.md#term-stagecontext) API and the report inputs are defined in [write-report](write-report.md#template-and-complete-inputs). Delivery adds nothing to them.

## Tests

Independent hooks: `publish_report` with a temporary destination, and `render_report` with fixture evidence. Cases: scientific FAIL preserved in the rendered file, duplicate publication, destination denial, interrupted publication, path traversal and a changed-bytes retry. Entry points and injectable failures: [test surfaces](../system/test-surfaces.md#verification-table).

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.delivery.AC-01 | PRD 3.9.4, N_deliver | deliver on fixture refs writes a directory whose manifest lists every file with relative path, sha256, size and source_ref, and every entry matches the stored bytes. | BLOCK |
| cap.delivery.AC-02 | N_deliver | A duplicate request id with identical bytes returns the committed manifest; different bytes return REQUEST_CONFLICT. | BLOCK |
| cap.delivery.AC-03 | N_deliver | Paths with parent traversal or absolute form are rejected; a destination denial returns DESTINATION_DENIED and exposes no partial directory. | BLOCK |
| cap.delivery.AC-04 | N_deliver | An interrupted publication leaves a recoverable staging record and never presents an incomplete directory as complete. | BOUNDARY |
| cap.delivery.AC-05 | PRD 3.9.3 | Rendering `research_report` to `research_report.md` and the POC bundle to a zip makes no model call and gives the same bytes on repeat. | BLOCK |
| cap.delivery.AC-06 | PRD 3.9.4 | publication.manifest.v1 is checked inside delivery as a deterministic manifest check, with no Gate and no Tier 2 call. | BLOCK |
| cap.delivery.AC-07 | N_deliver | Publication starts only after the report Verification and release are committed. | BOUNDARY |
| cap.delivery.AC-08 | US-01 | A complete fixture run ends with outputs/<run_id>/ holding report, POC bundle, empirical results, raw captures and an evidence index. | SYSTEM |
