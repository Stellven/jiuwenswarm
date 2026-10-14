# CC build coverage and checking assignments

**Reading level: human potential.** One row per capability capsule (CC). Each row says what the CC takes, what it produces, and how its output is checked. The exact fields, checks and criteria are on the linked tier 3 page.

## How every CC is checked

1. The worker CC produces its output. It runs its own self-review first. For example, the Intent CC checks its reading against the request.
2. The host runs the deterministic check bundle pinned to that CC version. These checks may read inputs and runtime records.
3. The verifier CC reads only the pinned declaration and the exact output. Its criteria are answerable from those two artifacts ([D24](decision-review.md#d24)). A CC with several outputs gets one verifier call per output.
4. The protected gate reads both results and accepts, rejects or halts.

The binder attaches the bundle and the checking profile from the chosen CC version. This is the same for the static template and for a planned DAG. The Planner cannot add, drop or weaken them. See [verifier](reference/capsules/verifier.md) and [run plan](reference/run-plan.md).

## Per-CC map

| CC | Takes | Produces | Host checks cover | Build page |
|---|---|---|---|---|
| Intent | Qualified intake | `intent_ir` | Schema, source spans, references | [Intent and Requirements](reference/intent-and-requirements.md) |
| Requirement | Accepted `intent_ir`, intake, default policy | `research_brief` | Schema, requirement links, default authorization | [Intent and Requirements](reference/intent-and-requirements.md) |
| Planner | Accepted Brief, library snapshot, resource inventory, plan policy | `plan_proposal` | Brief coverage, port types, dependencies, cycles, mandatory check bundles, permissions, resources, budgets | [Planner](reference/capsules/planner.md) |
| Search | Accepted Brief, search scope | `candidate_set` | Citations resolve to captured sources, excerpt hashes, idea count | [Search](reference/capsules/search.md) |
| Screening | Candidate set, Brief, pinned rubric | `screening_result`, `opportunity_card` | Score ranges, totals, tie rule, selection in candidate set | [Screening](reference/capsules/screening.md) |
| Hypothesis | Opportunity card, Brief, resource snapshots | `hypothesis_blueprint` | Metrics map to Brief targets, rules use declared metrics, boundaries do not overlap | [Hypothesis](reference/capsules/hypothesis.md) |
| Builder | Blueprint, resource snapshots, environment lock | `poc_manifest`, `poc_artifact_bundle` | Required files, syntax, forbidden modules, pinned dependencies, output format. Build evidence only. No trial runs | [Builder](reference/capsules/builder.md) |
| Research Benchmark | POC, build receipt, blueprint, resources, environment lock | `benchmark_payload` | Protocol and environment match, baseline before treatment, repeat counts, values match raw results | [Research Benchmark](reference/capsules/research-benchmark.md) |
| Scientific Evaluation | Blueprint, benchmark payload, Brief | `evaluation_verdict` | Recompute every rule from the blueprint and payload, registered rules only | [Scientific Evaluation](reference/capsules/scientific-evaluation.md) |
| Delivery | All accepted artifacts and gate decisions | `delivery_manifest`, `research_report` | Ref hashes, required sections, numbers match payload, verdict matches evaluation | [Delivery](reference/capsules/delivery.md) |
| Verifier | Declaration and exact output only | `verifier_assessment` | Assessment schema, subject identity, one finding per criterion | [Verifier](reference/capsules/verifier.md) |

## What the checks do not establish

The verifier does not judge request fidelity, source support or scientific validity. Fidelity and preservation are producer obligations of the Intent and Requirement CCs, backed by host span and reference checks. Scientific validity is the job of Scientific Evaluation, backed by rule recomputation. Platform benchmark cases measure how well this works over time.

## Ownership and completion

The CC owner defines ports and proposes per-CC checks and criteria. The Verifier owner owns check bundles and checking profiles. The Benchmark owner owns platform benchmark cases and labels. Capsule self-tests help development but never certify outputs.

Use one declaration loader, runner, check runner, verifier call and gate store for every CC. Reuse the built compiler where it fits. A generated module is a candidate until its assigned cases and connected boundaries pass. Whole-workflow acceptance needs connected end-to-end evidence.
