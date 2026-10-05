---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [launcher.extract_text]
consumes: [cc.type.intake, cc.type.source_text]
depends_on: [pipeline.md, ../types/source-text.md]
tags: [m1, module]
---

# Launcher source projection

Ordinary pure module `launcher.extract_text(intake) -> source_text` copies the normalized research prompt verbatim, supplies source reference/kind, hashes UTF-8 content, and fixes Unicode-code-point offset basis. It never reads arbitrary resources, invents missing text or invokes a model. Missing prompt returns INPUT_MISSING; invalid encoding/type returns INPUT_INVALID. [source_text](../types/source-text.md) owns the canonical shape.

The launcher validates and persists source_text as input evidence before Requirement Compilation. Identical requests reuse the committed projection; interrupted publication follows the store contract. Optional deterministic intent hints derive only from this text, require no semantic Gate or capsule admission, and cannot override source spans or the Brief. Ingestion documents/repository/datasets remain separately frozen resource inputs. This boundary follows explicit typed component inputs in [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/).
