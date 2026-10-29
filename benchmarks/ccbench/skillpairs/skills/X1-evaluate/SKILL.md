---
name: evaluate-preregistered-results
description: Evaluate repeated baseline and treatment measurements against pre-registered success and falsification rules, reporting per-metric and overall PASS, FAIL, or INCONCLUSIVE with numerical evidence.
---

# Evaluate pre-registered results

## When to use

Use when a researcher supplies metric-specific success and falsification rules
and repeated baseline and treatment measurements. Evaluate the supplied rules;
do not redesign the experiment or select thresholds after seeing the results.

## Method

1. **Extract the decision contract.** For each expected metric, record its name,
   units, direction, exact success predicate, exact falsification predicate,
   repeat aggregation, and any required sample counts or uncertainty procedure.
   Capture the pre-registered overall rule, including required metrics, weights,
   or exceptions. Preserve strict versus inclusive inequalities exactly.

2. **Check the measurements.** Match baseline and treatment repeats to the right
   metric and condition. List supplied values and usable counts. Identify missing,
   nonnumeric, nonfinite, or incompatible-unit values. Do not turn missing values
   into zero, fabricate repeats, discard outliers, or silently omit a metric.
   Apply only documented exclusion and missing-data rules. Missing required data
   makes affected decisions INCONCLUSIVE unless the registered procedure still
   permits a decision; continue evaluating unaffected metrics.

3. **Resolve how repeats enter the rule.** Use the registered statistic or
   procedure, including pairing and uncertainty requirements. Do not silently
   substitute a mean, median, best run, or significance test. If aggregation is
   unspecified, seek clarification and mark affected decisions INCONCLUSIVE.
   An explicitly authorized descriptive assumption may be used, but label the
   resulting verdict conditional on that assumption, not a registered conclusion.

4. **Calculate the decision quantities.** Show baseline and treatment summaries
   and the arithmetic producing them. Substitute the baseline into each threshold
   formula and show the resulting numerical threshold. Calculate differences,
   ratios, intervals, or other quantities only as required by the predicates.
   Use consistent units. Prefer exact decimal or rational arithmetic near a
   boundary; retain full precision for comparisons and round only for display.
   If a required ratio has a zero denominator or another operation is undefined,
   use a registered handling rule or mark that decision INCONCLUSIVE.

5. **Evaluate both predicates independently.** Record each as true, false, or
   unknown, with the numerical comparison that establishes it. Apply any
   pre-registered precedence rule; otherwise classify as follows:
   - Success true and falsification false: **PASS**.
   - Falsification true and success false: **FAIL**.
   - Both false: **INCONCLUSIVE**, because the result falls between the rules.
   - Either unknown: **INCONCLUSIVE** pending the missing information.
   - Both true: **INCONCLUSIVE** due to conflicting rules; expose the overlap
     rather than choosing a favorable interpretation.

6. **Combine the metric verdicts.** Apply the pre-registered overall rule exactly.
   If none is provided, label this fallback explicitly: overall FAIL if any
   required metric FAILs; otherwise PASS only if every required metric PASSes;
   otherwise INCONCLUSIVE. An empty or unknown required metric set is
   INCONCLUSIVE. Never silently drop an undecidable metric from the combination.

7. **Audit and report.** Check metric coverage, units, arithmetic, inequality
   boundaries, and overall aggregation. Separate measured evidence from any
   assumptions. Describe PASS and FAIL as outcomes under the stated rules,
   without claiming proof, causation, or unrequested statistical significance.

## Common pitfalls

- Treating failure to meet success as falsification, or lack of falsification
  as success; the two rules can leave an undecidable region.
- Reversing an inequality because of the metric's preferred direction; evaluate
  the actual predicates and flag contradictions with the stated direction.
- Comparing rounded numbers, changing inclusive boundaries, or interpreting
  a relative threshold as an absolute difference.
- Averaging paired ratios when the rule calls for a ratio of summaries, or
  inventing a test or multiplicity correction absent from the registration.

## Suggested output

State the aggregation and overall rules used, identifying any assumptions.
Provide one row per expected metric:

| Metric / units | Baseline repeats, count, summary | Treatment repeats, count, summary | Success calculation and truth | Falsification calculation and truth | Verdict / reason |
|---|---|---|---|---|---|

Include supporting arithmetic below the table when it will not fit clearly.
Finish with **Overall: PASS / FAIL / INCONCLUSIVE**, the combination applied,
and any specific missing information needed to resolve undecidable results.
