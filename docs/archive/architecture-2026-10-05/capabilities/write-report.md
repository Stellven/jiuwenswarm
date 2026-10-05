---
id: cap.research.write_report
type: capability
level: detail
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, ../../product/report-writer-upstream-2026-10-01.md]
provides: [research.write_report]
consumes: [cc.type.evaluation_verdict, cc.type.benchmark_payload, cc.type.research_brief, cc.type.idea_set, cc.type.opportunity_card, cc.type.hypothesis_blueprint, cc.type.research_report]
depends_on: [README.md, delivery.md, research-gates.md, measurement-protocol.md, ../types/research-report.md]
tags: [m1, contract, report]
prd: [3.9.1, 3.9.2]
---

# `research.write_report`: the research report

PRD: 3.9.1, 3.9.2

> Answers: How does the report capability turn the admitted evidence into one checked research_report?

## What it does

It writes the final `research_report` from the admitted evaluation, benchmark, brief, ideas, card and blueprint, using one fixed template and one brokered model [turn](../system/model-bridge.md#term-model-turn). It adds no new research. Scientific FAIL, contradictions and every recorded limitation stay in the report. The capability produces the `research_report` value only. [Delivery](delivery.md) renders `research_report.md` and the POC zip from it and publishes the directory.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-stagecontext"></a>**StageContext** | The bounded, read-only view of earlier run evidence the supervisor hands the report capability: references and short summaries of accepted outputs, scoped to the current call. |

## Where it sits

| | |
|---|---|
| <a id="term-flow-position"></a>**Flow position** | Task node in the research chain template ([capabilities](README.md)); the last work node before delivery |
| <a id="term-work-capsule"></a>**Work capsule** | `research.write_report`, a `skill` with a pinned template body and one model turn, no admitted nested dependencies |
| <a id="term-inputs"></a>**Inputs** | [`evaluation_verdict`](../types/evaluation-verdict.md), [`benchmark_payload`](../types/benchmark-payload.md), [`research_brief`](../types/research-brief.md), [`idea_set`](../types/idea-set.md), [`opportunity_card`](../types/opportunity-card.md), [`hypothesis_blueprint`](../types/hypothesis-blueprint.md) |
| <a id="term-output"></a>**Output** | [`research_report`](../types/research-report.md) |
| <a id="term-effect-class"></a>**Effect class** | `pure` for the capsule; the supervisor-supplied StageContext is read through the trusted broker |
| <a id="term-gate-profile"></a>**Gate profile** | shared `research.verifier` with `research.accept_report.v1` ([research gates](research-gates.md)) |
| <a id="term-build-step"></a>**Build step** | with the other research capabilities ([build order](../build-order.md), step 9) |

## Declaration

Abridged to the fields that matter. The format is in [capsule fields](../capsule/fields.md).

```json
{
  "identity": {"name": "research.write_report", "kind": "skill",
    "summary": "Write the research report from admitted evidence with a fixed template, preserving the scientific label and limitations."},
  "ports": {
    "inputs": [
      {"name": "evaluation_verdict", "type": "evaluation_verdict", "required": true},
      {"name": "benchmark_payload", "type": "benchmark_payload", "required": true},
      {"name": "research_brief", "type": "research_brief", "required": true},
      {"name": "idea_set", "type": "idea_set", "required": true},
      {"name": "opportunity_card", "type": "opportunity_card", "required": true},
      {"name": "hypothesis_blueprint", "type": "hypothesis_blueprint", "required": true}
    ],
    "outputs": [{"name": "research_report", "type": "research_report", "check_id": "report_template_complete"}]},
  "needs": {"external": [], "network": "none", "resources": {"max_model_turns": 1}},
  "evolution": {"rsi": "none", "may_change": []}
}
```

## Checks

| Check | Source | Meaning |
|---|---|---|
| template sections | type and [capsule](../capsule/capsule.md#term-capability-capsule) | the 8 required sections appear in order; empty sections stay visible |
| scientific label | [Tier 1](../verification.md#term-tier-1) deterministic | the report label equals the admitted evaluation label |
| citations | [Gate](../verification.md#term-gate) deterministic | every citation resolves to an `idea_set` source and its retained excerpt |
| numbers | Gate deterministic | each number recomputes from the admitted benchmark |
| limitations | Gate deterministic | all recorded material limitations from earlier stages are present |
| report faithful | Gate judged | findings, method and recommendations follow the admitted evidence and keep contradictions and scientific failure (`report_faithful`, see [research gates](research-gates.md)) |

## Template and complete inputs

The [verbatim upstream source](../../product/report-writer-upstream-2026-10-01.md) is retained under product inputs. Its installation and output-format instructions are source material; the M1 adaptation below governs.

Source verified: OpenJiuwen sciencediscovery commit `cee1974d463136aa611234e3f8a915a7dc57ae88`, `skills/report-writer/SKILL.md`, Default Report Template and Phases 2 to 4. The adapted static template is a body file of `research.write_report`. Required section order: 1. Executive Summary; 2. Knowledge Research [Findings](../schemas/finding.md#term-finding); 3. Data Analysis Findings; 4. Cross-Domain Insights; 5. Contradictions (Unresolved); 6. Limitations & Gaps; 7. Recommendations; Verdict. Methodology and benchmark analysis go in Data Analysis Findings. Unresolved contradictions are preserved. Empty or not-applicable sections remain visible. The source template's completeness labels COMPLETE, PARTIAL and FAILED are separate from the four scientific labels and from Gate verdicts. M1 uses this fixed format even where upstream permits customization; no upstream package installation instruction or `/mnt` output path carries into the product.

Report inputs include `idea_set`, `opportunity_card` and `hypothesis_blueprint` as recorded plan wires. A trusted `get_stage_context(run_id, through_step)` API in `cc/evidence.py` returns closed StageContext `{artifact_refs, observation_refs, verification_refs}`, scoped to completed [steps](../system/nodes.md#term-step) of the caller's run. It provides no hidden [fixtures](../system/test-surfaces.md#term-fixture), credentials or arbitrary file access. The report uses these refs to list earlier non-blocking issues and Gate limitations. The context is supervisor-supplied evidence, never a model-selected scope. Every citation must resolve to an `idea_set` source and its retained excerpt, and each number must match the admitted benchmark.

## Bounded synthesis design

The report is a skill with no admitted nested dependencies and one brokered synthesis turn. Its pinned instructions request only the declared `research_report` output. The handler and profile ceiling is one model call. A call request, an extra turn, malformed output or a failed factual or template check ends the attempt without regeneration. This is a provisional architecture default behind the admitted body and profile, not an executed quality claim or a turn count taken from the PRD. The [improvement guide](improvement.md) holds the improvement hypotheses and planted-defect [families](../contracts/principles.md#term-message-family).

## Tests

Independent hook: `render_report` with fixture evidence (the render itself is in [delivery](delivery.md)). Cases: scientific FAIL preserved, a missing section, a stale number, a stale citation, a dropped limitation, a template-skip instruction inside [source text](../types/source-text.md#term-source-text), and a second turn requested. Entry points and injectable failures: [test surfaces](../system/test-surfaces.md#verification-table).

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.write_report.AC-01 | PRD 3.9.2 | The report has the 8 required sections in order (Executive Summary through Verdict); empty sections stay visible; every number matches the admitted benchmark and every citation resolves to an [idea_set](../types/idea-set.md#term-idea-set) source. | BLOCK |
| cap.write_report.AC-02 | US-09 | A scientific FAIL verdict appears in the report unchanged, with all recorded limitations retained. | SYSTEM |
| cap.write_report.AC-03 | PRD 3.9.1 | The capability makes at most one model turn and performs no research; a call request, extra turn or malformed output ends the attempt without regeneration. | BLOCK |
| cap.write_report.AC-04 | PRD 3.9.2 | The StageContext supplied to the report holds only refs of completed steps of the run and no hidden fixture or credential. | BOUNDARY |
| cap.write_report.AC-05 | G_node | A report whose label differs from the admitted evaluation fails the report Gate and delivery does not start. | SYSTEM |
