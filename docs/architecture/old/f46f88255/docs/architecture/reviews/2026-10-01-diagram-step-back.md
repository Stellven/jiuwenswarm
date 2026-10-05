---
type: review
status: processed
tags: [review, step-back, diagram]
---

# Step back, 2026-10-01: drawing the overall system

The second step back, done by drawing [the overall system diagram](../system/diagram.md) from the pages alone, with every edge named by a defined datatype. Three parts could not be drawn as the pages stood:

| # | Finding | Disposition |
|---|---|---|
| 1 | Policy documents had no writer, and the vocabulary had two (the runner said admission; the toolchain said the vocabulary builder) | fixed: the vocabulary builder (M00a) and a new policy publisher (M00c) are the one writers |
| 2 | "The current" policy and vocabulary were undefined | fixed: `config.yaml` names them; the launcher and admission resolve them ([toolchain M00c](../capsule/toolchain.md#m00c-policy-publisher)) |
| 3 | The admission judge has no use at M1 | recorded as [open issue](../open-issues.md) 31 |

After the fixes, the lint's diagram check passed on its first run: every node is defined, every edge label is a defined datatype, every payload type is on an edge, and every M1 run-plan capsule is drawn.
