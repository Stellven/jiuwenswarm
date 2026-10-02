---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [research.write_report, research.deliver_report]
consumes: [cc.type.evaluation_verdict, cc.type.benchmark_payload, cc.type.research_brief, cc.type.research_report]
depends_on: [pipeline.md, ../types/research-report.md, op-workspace-io.md]
tags: [m1, blackbox]
---

> **Draft contract.** The source template is available. Only the mechanical delivery Gate exception (issue 36) remains an owner decision.

# `report_capsule` and delivery: `research.write_report`, `research.deliver_report` (PRD 3.9)

## What it does

One step writes the markdown report from the verdict, the benchmark and the Brief, in the report-writer template (3.9.1, 3.9.2). A second step writes the report and the POC files to the user's workspace, and the UI shows it (3.9.3, 3.9.4).

## Provisional interface

| | |
|---|---|
| **Step id** | `report`, then `deliver` |
| **Work capsule** | `research.write_report`, a `skill`; `research.deliver_report`, a `tool` |
| **Inputs** | [`evaluation_verdict`](../types/evaluation-verdict.md) from `evaluation`; [`benchmark_payload`](../types/benchmark-payload.md); [`research_brief`](../types/research-brief.md); for `report`, also idea_set, opportunity_card and hypothesis_blueprint; for `deliver`, research_report, poc_bundle and benchmark_payload |
| **Outputs** | [`research_report`](../types/research-report.md); `deliver` returns the written paths, as a `path` collection |
| **Operators it pins** | [`op.workspace_read`, `op.workspace_write`, `op.workspace_list`](op-workspace-io.md), for deliver |
| **Effect class** | `write_report`: `pure`. `deliver_report`: `idempotent`, writing only `fs:workspace/outputs/*` |
| **Gate capsule** | `research.accept_report`: judged criteria, intended: the report states the classification and its reason, invents no claim, and lists every limitation. `deliver` is gated by fixed checks: every file exists with the stored bytes |

## Known from the PRD

- The template is fixed (3.9.1).
- Markdown only (3.9.2).
- Files go to the workspace only, never to an outside channel (3.9.4).
- The run view closes the lifecycle (3.9.4).

## Assumptions

- `deliver` is a capsule, not control code: every node is a capsule, and its gate checks the files.
- Issue 36 proposes a fixed-only delivery Gate. Until approved, freeze refuses that mechanical plan; no trivial model judgement is invented.

## Waits on, and revise when

- The report-writer template.
- Whether a purely mechanical step like `deliver` must have a judged check, or the policy allows a gate of fixed checks only: [open issue](../open-issues.md) 36.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage owns all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor owns halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The owning output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/verification.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

## Template and complete inputs

The [verbatim upstream source](../../product/report-writer-upstream-2026-10-01.md) is retained under product inputs. Its installation/output-format instructions are source material; the M1 adaptation below governs the product.

Source verified: OpenJiuwen sciencediscovery commit `cee1974d463136aa611234e3f8a915a7dc57ae88`, `skills/report-writer/SKILL.md`, Default Report Template and Phases 2–4. Pin the adapted static template as a body file of research.write_report. Required section order: 1. Executive Summary; 2. Knowledge Research Findings; 3. Data Analysis Findings; 4. Cross-Domain Insights; 5. Contradictions (Unresolved); 6. Limitations & Gaps; 7. Recommendations; Verdict. Methodology and benchmark analysis go in Data Analysis Findings. Preserve unresolved contradictions. Empty/not-applicable sections remain visible. Source-template completeness labels COMPLETE/PARTIAL/FAILED are separate from the four scientific labels and Gate verdicts. M1 uses this fixed format even when upstream permits customization; no upstream package installation instructions or /mnt output path carry into the product.

Report inputs additionally include idea_set, opportunity_card and hypothesis_blueprint as recorded plan wires. A trusted `get_stage_context(run_id, through_step)` API in `cc/evidence.py` returns closed StageContext `{artifact_refs, observation_refs, verification_refs}`, scoped to completed steps of the caller's run; it does not provide hidden fixtures, credentials or arbitrary file access. The report uses these refs to enumerate earlier non-blocking issues and Gate limitations. This context is supervisor-supplied evidence, never a model-selected scope. Every citation must resolve to an idea_set source and retained excerpt; each number must match the admitted benchmark. No new research is performed.

Delivery inputs are research_report, poc_bundle and benchmark_payload plus the same authorized evidence context. Publish outputs/<run_id>/ as one recoverable manifest-backed directory containing research_report.md, POC_Artifact_Bundle.zip, empirical_results.json, raw stdout/stderr and an evidence index pointing to preserved blueprints/Gate decisions. Extract only validated four-role POC files. No partial directory is presented as completed. Duplicate identical requests return that publication; changed bytes conflict. Verify stored bytes, then expose them through native Web/TUI and /swarmflows. Do not send external notifications or alter scientific conclusions.
