---
type: payload-type
id: cc.type.research_report
version: 2
status: draft
tags: [types, m1]
---

> **Draft.** The upstream report-writer template has been located and source-checked. See the adaptation and evidence inputs on [Delivery](../m1/delivery.md).

# `research_report`: the user's report · version 2

The final markdown report: findings, method, benchmark analysis, the verdict and its limitations, and verified citations (3.9.2).

**Made by** the report step ([delivery](../m1/delivery.md)). **Read by** the delivery step, which writes it to the user's workspace and shows it in the UI.

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `markdown` | `text` | req | checked |  | The whole report, in the template's structure |
| `sections` | `list<string>` | req | checked |  | At least one. The section titles, in order; must include the method, the benchmark analysis and the limitations (3.9.2) |
| `classification` | `enum(PASS, FAIL, INCONCLUSIVE, CONDITIONALLY_ACCEPTABLE)` | req | checked |  | The evaluation's classification, so the user sees a scientific `FAIL` explained (3.8.5) |
| `citations` | `list<id>` | req | checked |  | The `source_id`s the report cites. May be empty |
| `limitations` | `list<text>` | req | checked |  | Every earlier output's `issues`, and the evaluation's residual risks |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |

## Example

```json
{
  "markdown": "# Tiled attention\n\n## 1. Executive Summary\nEvidence-scoped content.\n\n## 2. Knowledge Research Findings\nEvidence-scoped content.\n\n## 3. Data Analysis Findings\nMethod: paired baseline/treatment. Benchmark analysis: claim falsified.\n\n## 4. Cross-Domain Insights\nEvidence-scoped content.\n\n## 5. Contradictions (Unresolved)\nEvidence-scoped content.\n\n## 6. Limitations & Gaps\nEvidence-scoped content.\n\n## 7. Recommendations\nEvidence-scoped content.\n\n## Verdict\nScientific: FAIL. Report completeness: COMPLETE.",
  "sections": [
    "1. Executive Summary",
    "2. Knowledge Research Findings",
    "3. Data Analysis Findings",
    "4. Cross-Domain Insights",
    "5. Contradictions (Unresolved)",
    "6. Limitations & Gaps",
    "7. Recommendations",
    "Verdict"
  ],
  "classification": "FAIL",
  "citations": [
    "arxiv:2205.14135"
  ],
  "limitations": [
    "Tested at batch size 1 only."
  ]
}
```
