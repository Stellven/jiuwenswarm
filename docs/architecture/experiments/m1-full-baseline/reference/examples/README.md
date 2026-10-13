# Readable worked examples

These are synthetic illustrations, not recorded runtime passes. JSON is formatted and named by meaning. Exact source hashes/references resolve within this folder. Supporting contracts/context show the connections without pretending to be implemented infrastructure.

| Read in order | Lesson |
|---|---|
| [Request](Request.txt), [Intent IR](Intent_IR.json), [checks](Intent_Checks.json), [assessment](Intent_Assessment.json), [decision](Gate_Decision.json) | Purpose/result are usable; checks allow semantic assessment; only protected decision authorizes acceptance |
| [Topic request](Request_Topic_Only.txt), [candidate](Intent_Topic_Only.json), [checks](Topic_Checks.json), [assessment](Topic_Assessment.json), [halt](Gate_Topic_Halt.json) | Valid shape and faithful extraction do not make missing intent actionable |
| [Conflicting request](Request_Contradictory.txt), [candidate](Intent_Contradictory.json) | Preserve required contradictions, request correction and halt rather than silently choose a constraint |
| [Research Brief](Research_Brief.json), [default policy](Default_Policy.json), [checks](Requirements_Checks.json), [assessment](Requirements_Assessment.json), [decision](Gate_Requirements_Pass.json) | Requirements preserves accepted meaning, marks assumptions and supplies planning/evidence obligations |
| [Scientific verdict](Evaluation_Verdict.json), [assessment](Science_Assessment.json), [gate](Gate_Science_Pass.json) | Scientific FAIL is correctly assessed and can receive infrastructure PASS for Delivery |
| [CC declaration](Capsule_Declaration.json) | Typed ports, implementation pins, effects and budget describe reusable work, not gate authority |

The numeric default/budget/science values are illustrative, not architecture-wide thresholds. The example Brief intentionally omits resource binding: it demonstrates compilation, not a ready empirical run. Later binding rejects missing required baseline/validation resources. The compact science example is not a complete Benchmark Payload or executed lifecycle. JSON-valid unsupported claims still require a failing semantic verdict; malformed structures fail before review.

[Example index](index.json) assigns exact schemas where specified. A runtime system must add trusted metadata, checking custody and successful persistence; copying an example decision grants no authority. The [inspection design](../../artifact-inspection.md) requires a UI or Markdown view of those same records.
