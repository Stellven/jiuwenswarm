---
id: cap.extract-text
type: module
status: draft
version: 2
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [launcher.extract_text]
consumes: [cc.type.intake, cc.type.source_text]
depends_on: [README.md, ../types/source-text.md]
tags: [m1, module]
level: detail
prd: [3.1.1]
---

# Source projection (intake module)

PRD: 3.1.1

> Answers: How does intake project the research prompt into source_text for the intent step?

## What it does

Ordinary pure module `launcher.extract_text(intake) -> source_text` copies the normalized research prompt verbatim, supplies source reference/kind, hashes UTF-8 content, and fixes Unicode-code-point offset basis. It never reads arbitrary resources, invents missing text or invokes a model. Missing prompt returns INPUT_MISSING; invalid encoding/type returns INPUT_INVALID. [source_text](../types/source-text.md) defines the canonical shape.

## Interface (intake calls)

Schema: `library-rsi-v1.schema.json#intake_request` is the `launch(prompt, channel, workspace)` call from the CLI or web entry adapter ([lifecycle](../system/lifecycle.md)); optional `resources` repeats the `intake.resources` entries. `library-rsi-v1.schema.json#intake_result` is its reply: the run id and the Refs of the recorded `intake` and `source_text` artifacts. Resource freezing is a separate call, `library-rsi-v1.schema.json#resource_snapshot_request` / `library-rsi-v1.schema.json#resource_snapshot_result`, described in [measurement protocol](measurement-protocol.md#frozen-methods). How resources are bound before qualification (CLI flags, input folder scan) is not yet specified; `resources` stays optional until it is.

Intake validates and persists [source_text](../types/source-text.md#term-source-text) as input evidence before the intent call dispatches; it is the input of the intent call and a text input of the requirement call. Identical requests reuse the committed projection; interrupted publication follows the store contract. Ingestion documents/repository/datasets remain separately [frozen](../system/lifecycle.md#term-freeze) resource inputs. This boundary follows explicit typed component inputs in [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/).

## Tests

Identical requests must reuse the committed projection; missing prompt must return INPUT_MISSING and invalid encoding or type INPUT_INVALID. Entry points and injectable failures: [test surfaces](../system/test-surfaces.md).

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.extract-text.AC-01 | PRD 3.1.1, N_intake | extract_text returns source_text whose text equals the normalized prompt byte for byte, with a UTF-8 content hash and code-point offset basis. | BLOCK |
| cap.extract-text.AC-02 | N_intake | A missing prompt returns INPUT_MISSING; invalid encoding or type returns INPUT_INVALID; no model is called. | BLOCK |
| cap.extract-text.AC-03 | N_intake | Identical requests reuse the committed source_text projection. | BOUNDARY |
| cap.extract-text.AC-04 | N_intake | extract_text never reads resources beyond the prompt. | BLOCK |
| cap.extract-text.AC-05 | US-01 | Intake persists source_text as input evidence before the intent call starts. | SYSTEM |
