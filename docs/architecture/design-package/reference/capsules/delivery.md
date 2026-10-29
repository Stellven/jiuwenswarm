# Delivery CC (`research.delivery`)

`Tier 3 · Part of: [Reference](../README.md)`

**Summary for reviewers.**
- Delivery is the leaf node, and an M1 plan has exactly one. It writes one markdown report and one manifest that lists every lifecycle artifact with its hash, role and audience.
- The report has nine fixed sections in a fixed order. Numbers come only from the benchmark payload. The verdict comes only from the saved evaluation verdict.
- A scientific negative result (`FAIL` or `INCONCLUSIVE`) is delivered normally. Delivery never softens or reverses a verdict.
- Recommendations live only in section 8 and carry a label. Everything else is observation.
- The report's limitations section carries the verdict's `blockers`, `residual_risks` and review notes, and section 8 carries its `followups`, all verbatim.
- Gate decisions reach Delivery as one host-built `gate_decision_index`, because a declaration port carries one artifact.
- The worker reads only its bound inputs. Five host records carry the files it lists but does not read.
- A failed blocking check or criterion halts the node and keeps the candidate and its evidence. Nothing retries it.
- The host checks hashes, headings, numbers and verdict text. The semantic verifier judges only coherence of the output. It runs once for each output, the manifest and the report, with the same declaration.

## Purpose and place in the run

Delivery writes the final report and manifest. It consumes only gate-accepted artifacts. It reports a scientific `FAIL` as faithfully as a pass. It does not measure, re-evaluate or fetch anything.

PRD mapping: PRD section 3.9 (3.9.1 to 3.9.4), user stories US15 and US16. The PRD names the capability `report_capsule.md` and the template `sciencediscovery/report-writer`. This design keeps the nine-section structure below as that static template.

## Declaration

Example: [delivery_capsule.json](../examples/delivery_capsule.json), valid against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name | `research.delivery`, kind `agent` |
| Inputs | thirteen ports, see Inputs. Each port carries one artifact |
| Outputs | `delivery_manifest`, `research_report`. The verifier runs once for each output, each time with this same declaration |
| Effect class | `read_only` (model call only). The trusted host, not the worker, copies exported files into the user workspace |
| Network | none |
| Budget | 120 s wall, one invocation, no tool calls |
| Pinned checks | declared: `delivery_manifest_schema`, `research_report_schema`, `required_sections`, `recommendation_labeling`. The protected binder adds the host checks listed below |

## Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `brief` | `research_brief` | Requirements CC | yes | Objective and constraints for section 1 |
| `candidate_set` | `candidate_set` | Search CC | yes | Citation text for section 2 |
| `opportunity_card` | `opportunity_card` | Screening CC | yes | Opportunity statement, citation IDs, risks |
| `hypothesis_blueprint` | `hypothesis_blueprint` | Hypothesis CC | yes | Claim and registered criteria for section 3 |
| `poc_manifest` | `poc_manifest` | Builder CC | yes | POC files for sections 4 and 9 |
| `benchmark_payload` | `benchmark_payload` | Research Benchmark CC | yes | Only source of numbers in section 5 |
| `evaluation_verdict` | `evaluation_verdict` | Scientific Evaluation CC | yes | Only source of the verdict, blockers, residual risks, review notes and follow-ups |
| `gate_decision_index` | `gate_decision_index` (`gate-decision-index:field-contract:1`) | Scheduler (`host_record` key `gate_decision_index`) | yes | One record that lists the node-scope gate decisions of this Delivery node's ancestors, listed in the manifest. In M1 the ancestors are every node of the plan before Delivery. |
| `screening_result` | `screening_result` (`screening-result:field-contract:2`) | Host record of the accepted Screening output (`host_record` key `screening_result`) | yes | Listed in the manifest with role `screening` and in `artifact_refs` |
| `execution_receipt` | `execution_receipt` (`execution-receipt:field-contract:1`) | Host record of the accepted Benchmark output (`host_record` key `execution_receipt`) | yes | Hardware and run facts for section 9. Its run records name the raw evidence files (`stdout_ref`, `stderr_ref`, `empirical_results_ref`) that the manifest lists with role `raw_evidence` |
| `provisioning_receipt` | `provisioning_receipt` (`provisioning-receipt:field-contract:1`) | Host record of the accepted Benchmark output (`host_record` key `provisioning_receipt`) | yes | Runtime facts for section 9, such as the interpreter version and the installed packages |
| `environment_lock` | `environment_lock` (`environment-lock:field-contract:1`) | Host record of the run's prepared lock (`host_record` key `environment_lock`) | yes | Listed in the manifest with role `environment` and in section 9 |
| `run_configuration` | `run_configuration` (`opaque-bytes`) | Host record of the frozen run configuration (`host_record` key `run_configuration`) | yes | Listed in the manifest with role `environment` and in section 9. Delivery lists it by Ref and does not read inside it |

The declaration schema gives a port no cardinality, so a port carries exactly one artifact. A run has many gate decisions. The scheduler therefore builds one `gate_decision_index` from the accepted dispatch records and hands it in on a single port. Delivery never builds the index itself.

The worker reads only its bound inputs. It has no tool calls and no store access. It writes the whole manifest from those inputs. Every Ref and hash in the manifest comes from a bound input or from a Ref inside one, such as the run records of the `execution_receipt` and the `archive_ref` of the `poc_manifest`. The host checks below read the run artifact store, not the worker.

### gate_decision_index

Purpose: the list of node-scope gate decisions that admitted each node before Delivery. It holds Refs only and no copied decision content.

`gate-decision-index:field-contract:1` (version 1.0.0) · Producer: scheduler, a host record built from accepted dispatch records. Consumers: Delivery CC, Delivery checks.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | `1.0.0` | Format version |
| `id` | `string` | yes | `gate_decision_index` | Record identity |
| `run_plan_ref` | `Ref` | yes | The frozen run plan of this run | The plan whose accepted attempts the index lists. Set by the scheduler, never by the Delivery CC. |
| `entries` | `GateDecisionEntry[]` | yes | 1 to 12 items. `node_id` values unique. In a real run one entry for each node whose attempt was accepted before Delivery starts, in run plan topological order | The advancing gate decisions of the run. Built by the scheduler at Delivery dispatch. Delivery reads it and must not extend or reorder it. |

**GateDecisionEntry**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `node_id` | `string` | yes | Pattern `^[a-z][a-z0-9_]{0,31}$`. A node of the run plan | The node whose attempt was accepted. A node ID of the frozen run plan. |
| `gate_decision_ref` | `Ref` | yes | A node-scope gate decision (`scope_kind` `node`) with action `advance` for that node | The decision that admitted the node's output. A Ref only. Delivery copies it into the manifest and does not read the decision. |

**Invariants**

- Every entry names a node of the run plan once, in run plan topological order.
- Every entry's decision is a node-scope decision with action `advance` for that node.
- In a real run there is one entry for each node accepted before Delivery starts, and no other.

**Producer obligations (scheduler)**

- Build the index from the accepted dispatch records of the run, at Delivery dispatch.
- Copy only Refs. Never copy or summarize decision content.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `output_structure` | The index matches `gate-decision-index:field-contract:1`, and node IDs are unique and in the run plan | Delivery is not dispatched |
| `entries_are_advancing_node_decisions` | Each entry's decision has `scope_kind` `node`, action `advance` and the entry's `node_id` | Delivery is not dispatched |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails, or an entry is missing | Delivery is not dispatched. The run halts | The accepted outputs and their decisions |

Examples: [valid](../examples/gate_decision_index.json). The synthetic example lists one entry (`evaluation`), because only that node has a node-scope gate decision example.

**Minimum quality bar.** Delivery can prove that every stage it reports was admitted, from Refs alone.

## Output field contract

### delivery_manifest

Contract ID `delivery-manifest:field-contract:2` (bumped from 1: added `gate_decision_refs`, `role`, a fixed audience enum and constraints).

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | string | yes | equals `2.0.0` | Format version |
| `id` | string | yes | `delivery_manifest` | Artifact identity |
| `brief_ref` | Ref | yes | equals the accepted Brief Ref | Brief the run answered. Copied from the `brief` input. Check `manifest_completeness` rejects any other Ref. |
| `verdict_ref` | Ref | yes | equals the accepted `evaluation_verdict` Ref | Saved verdict this delivery reports. Copied from the `evaluation_verdict` input. The report agrees with that verdict and never changes it. |
| `report_ref` | Ref | yes | equals the `artifact_ref` of the single `files` entry with role `report` | The report. Delivery writes the report first, then computes its sha256, then writes the manifest (producer obligation 1). Check `ref_hash_match` compares the hash. |
| `gate_decision_refs` | Ref[] | yes | min 1 item. Equals the `gate_decision_ref` values of the `gate_decision_index` input, in the same order | Evidence that each stage was admitted. Copied from the `gate_decision_index` input, never built by the CC. Holds Refs only. |
| `artifact_refs` | Ref[] | yes | min 7 items. Must include `candidate_set`, `screening_result`, `opportunity_card`, `hypothesis_blueprint`, `poc_manifest`, `benchmark_payload` and `evaluation_verdict`. No duplicate `id` | Every lifecycle record of the run. The CC takes each Ref from a bound input and lists each artifact once. Hashes come from the inputs and are never recomputed. |
| `files` | DeliveryFile[] | yes | min 12 items. Unique `path`. Role coverage below | Every file exported to the output directory. The CC lists them. The trusted host copies them into the user workspace, not the CC. A file for neither audience is not listed. |
| `missing_evidence` | MissingEvidence[] | yes | empty list when nothing is missing. Any `blocking: true` item blocks release | Omissions and redactions. Lists each artifact that is unavailable or withheld, with a reason and a `blocking` flag. An empty list means nothing is missing. A `blocking` item halts the Delivery node and blocks release. |
| `ext` | object | no | none | Extension data written by the Delivery CC. Consumers may ignore it. It never changes the meaning of the manifest or the outcome of a check. |

Role coverage in `files`: exactly one `report`, `brief`, `candidate_set`, `screening`, `opportunity`, `hypothesis`, `poc_manifest`, `poc_bundle`, `benchmark` and `verdict`. At least one `gate_decision`. At least two `raw_evidence` (baseline and treatment execution records). At least two `environment` (environment lock and run configuration).

**DeliveryFile** (new type, one row of `files`)

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `path` | string | yes | relative, lowercase, pattern `^[a-z0-9_][a-z0-9_./-]*$`, no `..` segment, unique in the manifest | Where the file sits in the output directory. The CC chooses it within the pattern. The user-visible report name is `research_report.md` unless the user named another file. |
| `artifact_ref` | Ref | yes | `sha256` equals the hash of the file bytes | Exact content identity. `sha256` is the hash of the file bytes, taken from a bound input or from the report Delivery just wrote. Check `ref_hash_match` compares it with the stored bytes. |
| `media_type` | string | yes | one of `text/markdown`, `application/json`, `text/plain`, `application/zip`, `text/x-python` | Format of the file, from the fixed list. The Delivery CC picks the type that matches the file bytes. No role-to-type mapping is enforced in M1. Readers use it to display the file, never to decide trust. |
| `role` | string | yes | enum `report`, `brief`, `candidate_set`, `screening`, `opportunity`, `hypothesis`, `poc_manifest`, `poc_bundle`, `environment`, `raw_evidence`, `benchmark`, `verdict`, `gate_decision` | What the file is in the research lifecycle. The role coverage rules above say how many files of each role must appear. `manifest_completeness` checks them. |
| `audience` | string | yes | enum `researcher`, `reviewer` | Who may read it. `researcher` is the requesting user. `reviewer` adds authorized reviewers. Files for neither audience are not exported. The CC sets it as the contract allows and never widens it. |

Examples: [valid](../examples/delivery_manifest.json) · rejected by `ref_hash_match`: [delivery_manifest_invalid_hash_mismatch](../examples/delivery_manifest_invalid_hash_mismatch.json)

The user-visible file name is lowercase `research_report.md`, unless the user explicitly named another file. PRD spellings such as `Evaluation_Verdict.json` map to the lowercase internal names.

### research_report

Contract ID `research-report:field-contract:1`. The report is a markdown file. Its structure is the contract. A line starting `# ` gives the title. Then the nine sections below appear once each, in this order, with this exact heading text (a level-2 heading, `## `). Every section is non-empty. No other level-2 heading is allowed.

| Heading | Required content |
|---|---|
| `## 1. Objective` | Research objective in the Brief's words. Constraints from the Brief. Source file name |
| `## 2. Opportunity and citations` | Opportunity statement from the card. A table with one row per `citation_id` on the card: citation ID, source, locator, excerpt, taken from the `candidate_set`. Every `citation_id` appears |
| `## 3. Hypothesis and registered criteria` | Claim, mechanism, independent variable, repeat count and seed. A table with one row per registered metric: `metric_id`, unit, aggregation, success rule, falsification rule, residual classification. A sentence saying the rules were registered before any measurement |
| `## 4. Method and POC` | Order of runs (baseline first, treatment second), the matched conditions, the bounded change, and the POC files and bundle names |
| `## 5. Results: baseline vs treatment` | A table with columns `Metric`, `Unit`, `Baseline`, `Treatment`, `Delta`, one row per registered metric. Values equal `baseline_value`, `treatment_value` and `delta` in the payload. Observations only. Names of the raw evidence files. Any `missing_evidence` of the payload is stated |
| `## 6. Scientific verdict and reasoning` | First non-empty line is `Classification: <value>` where value is one of `PASS`, `FAIL`, `INCONCLUSIVE`, `CONDITIONALLY_ACCEPTABLE` and equals the verdict `classification`. The next two lines are `Completeness: <status>` and `Plausibility: <status>` with the verdict `completeness.status` and `plausibility.status`. Then one line per finding `- <metric_id>: <classification>. <rationale>` as in the verdict, in verdict order |
| `## 7. Limitations and risks` | The limitations section. It draws from the verdict. One bullet each, verbatim: every string of `blockers`, every string of `residual_risks`, every note of `completeness.notes` and every note of `plausibility.notes`. Then every risk on the opportunity card, bullet prefixed `Risk from the opportunity card:`. Nothing that claims the hypothesis is supported when the verdict is not `PASS` |
| `## 8. Follow-up recommendations` | One bullet per verdict `followups` string, verbatim, each bullet beginning `Recommendation:`. Delivery may add more bullets with the same label. A recommendation never restates a result as new evidence |
| `## 9. Reproducibility` | Seed, repeat count, hardware and runtime file, and the rerun steps (install the pinned lock, extract the POC bundle, run `run_benchmark.py` under the same configuration and seed). A table `Item`, `Id`, `sha256` with a row for the Brief, blueprint, POC manifest, POC bundle, environment lock, run configuration, benchmark payload and verdict |

Rules for the whole report:
1. The report never contradicts the saved verdict. It may explain the verdict. It may not change or qualify the classification.
2. Observations (measured values, registered rules, verdict findings) are separate from recommendations. The label `Recommendation:` appears only in section 8, and every bullet in section 8 carries it.
3. A scientific negative result is reported in the same structure and tone as a positive one. Section 6 states it plainly.
4. Every number comes from the benchmark payload or the blueprint. No rounding, no recomputation.
5. The report states nothing about runs that did not happen. It never claims a result for an unmeasured metric.

Examples: [valid report](../examples/research_report.md)

## Producer obligations

1. Read the bound inputs and nothing else. Write the report first, then compute its sha256, then write the manifest.
2. Copy numbers, rules, verdict strings, blockers, residual risks, review notes, follow-ups and citations from the source artifacts. Do not paraphrase the verdict classification.
3. Self-review before output. Re-read the Brief objective and confirm section 1 matches. Compare each results row with the payload. Compare section 6 with the verdict. Confirm every blocker, residual risk, completeness note, plausibility note and follow-up of the verdict appears. Confirm every `Recommendation:` label sits in section 8. Confirm the manifest lists each lifecycle artifact once.
4. Do not edit, redact or omit evidence silently. If an artifact is unavailable or withheld, list it in `missing_evidence` with a reason and `blocking`.
5. Do not run experiments, fetch sources or change the verdict. Do not write outside the declared outputs.
6. Set `audience` for each file as the contract allows. Never widen it.
7. State no conclusion stronger than the verdict. Cite only accepted refs, and copy each number from the payload ([D32](../../method/decisions.md#d32)).

## Deterministic check bundle

The host runs these before the verifier. The first four are also declared in the CC. Every failure is a blocking failure. It halts the node. Nothing retries it.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `delivery_manifest_schema` | Manifest matches `delivery-manifest:field-contract:2`. Enums, path rule, role coverage and `ext` as above | reject, node halts |
| `research_report_schema` | Report is valid UTF-8 markdown with a title line `# ` | reject, node halts |
| `required_sections` | The nine headings of the table appear exactly once, in order, each with non-empty body. No other level-2 heading | reject, node halts |
| `recommendation_labeling` | `Recommendation:` appears only in section 8. Every bullet in section 8 starts with it | reject, node halts |
| `ref_resolves` | Every Ref in the manifest resolves to bytes in the run artifact store | reject, node halts |
| `ref_hash_match` | Every Ref `sha256` and every `files[].artifact_ref.sha256` equals the sha256 of the stored bytes. `report_ref` equals the report file hash | reject, node halts |
| `manifest_completeness` | `brief_ref` and `verdict_ref` equal the accepted inputs. `gate_decision_refs` equal the run's advancing decisions. `artifact_refs` and `files` roles cover the lifecycle as in the contract, including the `screening_result`, `environment_lock` and `run_configuration` inputs and the raw evidence Refs of the `execution_receipt` | reject, node halts |
| `results_table_matches_payload` | Each row of the section 5 table has a payload metric and each payload metric has a row. Baseline, treatment and delta equal the payload numbers (numeric equality) | reject, node halts |
| `criteria_match_blueprint` | Section 3 table has the blueprint's metric IDs, units and aggregations, no more and no fewer | reject, node halts |
| `verdict_matches_evaluation` | `Classification:` string equals the verdict `classification`. The `Completeness:` and `Plausibility:` lines equal the verdict statuses. Each finding line matches the verdict finding for its metric | reject, node halts |
| `carried_content` | Every verdict blocker, residual risk, completeness note and plausibility note appears verbatim in section 7. Every verdict follow-up appears verbatim in section 8. Every opportunity risk appears in section 7. Every card `citation_id` appears in section 2 | reject, node halts |
| `reproducibility_pins` | The section 9 table rows equal manifest Refs for the same IDs and hashes. All eight required rows present | reject, node halts |
| `negative_result_delivered` | When classification is `FAIL` or `INCONCLUSIVE`, a report and manifest still exist and no `blocking` missing evidence hides the cause | reject, node halts |

A failed blocking check halts the node and keeps the candidate output, its evidence and the check results (see Failure outcomes). There is no retry budget.

Note on the invalid pair for `required_sections`: a report without section 7 also lacks the blockers and residual risks that `carried_content` requires. `required_sections` fires first.

## Verifier criteria

The verifier runs once for each output artifact, the `research_report` and the `delivery_manifest`, each time with the same pinned declaration and the same checking profile. It sees only the declaration and that one output. It cannot compare the report with the payload or verdict. Those comparisons are host checks above. The verifier works with reduced assurance because of that. The generic criteria of the checking profile apply to both runs.

| Criterion ID | Output | Question | Blocking |
|---|---|---|---|
| `sections_coherent` | `research_report` | Does each of the nine sections contain content that fits its heading, and does the report read as one coherent document? | yes |
| `limitations_consistent_with_verdict` | `research_report` | Do the limitations and risks fit the classification stated in section 6 of the same report? A `FAIL` report must not describe the hypothesis as supported. A `PASS` report must not describe it as refuted | yes |
| `recommendations_separated` | `research_report` | Is every recommendation labeled and confined to section 8, and is every statement in sections 1 to 7 an observation or a registered rule rather than advice? | yes |
| `report_internally_consistent` | `research_report` | Do the numbers and metric names in sections 3, 5, 6 and 9 agree with each other inside the report? | yes |
| `manifest_report_coherent` | `delivery_manifest` | Does the manifest list exactly one file with role `report`, and are the audiences and roles plausible for each file name? | no |

## Gate rule

Accept when every deterministic check passes and no blocking criterion fails. The gate then advances the run to lifecycle closure, which exports the manifest files to the user workspace. A scientific `FAIL` or `INCONCLUSIVE` verdict does not affect acceptance. Reject on any failed check or blocking criterion. A rejection halts the node, keeps the candidate output and evidence, and starts no retry. Halt the run also when `missing_evidence` has a `blocking` item.

## Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| Hash or Ref check fails | node halts, dispatch outcome `rejected` | all inputs, rejected outputs and check results |
| Required section missing or out of order | node halts, dispatch outcome `rejected` | rejected report and manifest |
| Report verdict differs from the saved verdict | node halts, dispatch outcome `rejected`. The saved verdict is never altered | rejected report, saved verdict |
| Blocking `missing_evidence` | node halts, dispatch outcome `halted`, release blocked | manifest draft and the reason |
| Verifier blocking criterion fails | node halts, dispatch outcome `rejected` | verifier assessment and rejected outputs |
| Input artifact absent or not gate-accepted | node does not start, run halts | run record |

## Examples

| File | Kind | Rejected by |
|---|---|---|
| [delivery_capsule.json](../examples/delivery_capsule.json) | valid declaration | none |
| [delivery_manifest.json](../examples/delivery_manifest.json) | valid manifest | none |
| [research_report.md](../examples/research_report.md) | valid report | none |
| [gate_decision_index.json](../examples/gate_decision_index.json) | valid host input record | none |

| [delivery_manifest_invalid_hash_mismatch.json](../examples/delivery_manifest_invalid_hash_mismatch.json) | invalid manifest | `ref_hash_match` |



The synthetic run has one node-scope gate decision example (`gate_science_node_pass.json`). The synthetic `gate_decision_index` lists only that decision. A real run lists the node-scope decision of every accepted node.

## Future seams

- The nine-section template is static in M1. A later version may add template variants (paper, poster) by adding a `template_id`. The M1 contract stays valid as the default.
- `audience` can grow new values for external release, with an authorization check owned by the PRD owner.
- Reports for several opportunities or hypotheses would repeat sections 2 to 6 per hypothesis. The manifest already lists artifacts by role, so it needs no change.
- Another delivery capsule can replace this one if it keeps the manifest contract and the host checks.

## M1 placement

The CC page above does not depend on where Delivery runs. In M1 the rules below apply.

- Delivery is the leaf of the plan. Every leaf of a plan is a Delivery node, and an M1 plan, static or planned, has exactly one ([D28](../../method/decisions.md#d28)). The leaf carries every Brief deliverable.
- It runs after the gate that accepted the Scientific Evaluation output. It always runs, including after a scientific `FAIL`.
- Enforced by the protected binder check `delivery_leaf_coverage` ([D42](../../method/decisions.md#d42)).
