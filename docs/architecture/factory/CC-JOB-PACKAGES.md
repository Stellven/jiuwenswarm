# Job-oriented CC package revision

This revision follows the user's clarified boundary: a CC is a useful package for
a job, and may contain tools, several components, skills, methods, references and
verification units together. Two CCs can be used in one node when each contributes
a distinct responsibility. There is no one-CC-per-node restriction. Avoid requiring
an agent to alternate between tightly coupled packages to complete one job.

The earlier `cc-library-review` directory remains a dated review of the preceding
versions. This document describes the revised package boundaries and supersedes
its taxonomy as a packaging recommendation; historical experiment evidence is unchanged.

## Revised packages

| Package/version | Job | Contents and completion boundary |
|---|---|---|
| `engine.strata_prefill_workbench` 1.1.0 | Investigate and test one admitted native prefill intervention | Component description, integration skill, experiment method, evidence access, analysis/design, profile transforms, explicit independent qualification, direct experiment or durable cycle operations, domain unit and development workflow checks. Ends in verified scoped evidence, a justified stop or a saved next-input proposal. |
| `factory.inference_lab` 1.1.0 | Interpret lab evidence and choose/test the next intervention | Job skill, report/observer/trace analysis, hypothesis/ablation/followup methods, prefill and drafting configuration components with integration instructions, evidence access, admitted loop and observer operations, scoped verification descriptions. Ends in retained reasoning, an admitted experiment/review cycle or an explicit prerequisite handoff. |
| `engine.expert_streaming` 2.1.0 | Integrate and evaluate a component from the expert-streaming family | Preserved eight component packages/patches, source map, applicability/engagement tools, bundled integration/repair/preflight/A-B skills, evidence/inspection/build/lab tools, development verification units. No separate integration/builder/lab CC must be interlaced for this job. Historical llama patches are not silently treated as Strata implementations. |
| `factory.integration_skill` 1.1.0 | Carry a generic authorized source change through integration/build/evaluation | Formerly passive skill becomes a mixed package: contextual integration/repair/preflight skills, evidence, source/image inspection, build lifecycle and lab/A-B lifecycle tools, development verification units. Source changes remain explicit agent work in the authorized checkout; the package does not automatically patch or commit. |

The four packages expose 20,24,20 and18 selected capabilities respectively. These
counts describe composed interfaces, not that many new implementations or methods.
No new top-level CCs were needed. The catalog remains23 top-level packages plus
eight nested components. The generic integration package now has tools, leaving
ten materials-only entries. Existing focused CC IDs remain available for genuinely
narrow jobs and compatibility; prior sealed releases and recorded results are retained.

## Composition without implementation forks

`jiuwenswarm/factory/job_packages.py` supplies a finite alias map and common native
wrapper. Each package fixes its own ID in its entrypoint; callers cannot supply
arbitrary backend operations. Tools reuse the existing scoped API, store, queue,
inspector, builder, lab adapters and method implementations. The job package is
contained from the agent's workflow perspective, not a claim of a hermetic OS
runtime: factory Python modules, store, host queue, engine/model and deployment
bindings remain explicit dependencies.

Selected-capability grants still apply. Querying or analyzing a report does not
require or acquire a sibling execution tool's GPU grant. Tools that submit GPU
work declare it explicitly. Contracts, exact source/image identity, task scope,
cycle budgets, quiet barriers and independent result checks still apply. Submission
must be followed by ending the agent turn so control can stop during measurement.

Source integration skills have one canonical copy in `integration_skill`, bundled
inside `expert_streaming` so an agent need not retrieve another package to read
them. Tests enforce byte equality. The expert package also bundles its A/B method;
nested component descriptor and patch bytes are unchanged. This is explicit
packaging reuse with a checked maintenance rule, not divergent implementations.

## Example: prefill job within one package

Using only `engine.strata_prefill_workbench`, an agent can:

1. `query/read` previous evidence, `inspect` the frozen scope, then `diagnose`,
   `test_scope` and `ablation` as needed. Read the bundled component/integration material.
2. `apply/verify_profile` a candidate. If the task requires qualification,
   `qualify_profile` retains the pair, independently verifies its invariant and
   assesses the explicit operator policy. Each verification/assessment record is
   still retained and inspectable; a single capability does not conflate their claims.
3. `loop_status/select/execute` an exact already-admitted template, then end its
   turn. Alternatively use direct `submit/status/result` for an admitted current-task
   contract, never both routes for the same experiment.
4. Resume, `collect/read` the independently verified result, and publish its decision
   or `followup` proposal. Confirm, revise or stop according to the evidence.

A different CC may be useful if numerical divergence requires a new instrumentation
component, or if an unrelated source/build job is required. That is a meaningful
handoff, not routine alternation just to access evidence or submit the same job.
For mixed nodes, the agent can freely select complementary packages within grants.

## Verification and functional corrections

- A supported prefill profile policy still checks only its named configuration
  capabilities; it does not certify every new sibling tool or authorize execution.
  Its local implementation identity now includes the composition module. Old
  certificates do not automatically qualify revised releases/modules.
- Development units attached to the job packages describe actual Host-call workflow,
  material consistency, scope and effect tests. Simulated build/lab seams are labeled;
  none establishes model quality, hardware efficacy or full job certification.
- Generic diagnosis now recognizes nested `report`/`analysis` and `cells` envelopes,
  preserves explicit scoped correctness failure, and reports available prefill
  measurements. It does not invent prompt/configuration identities or A/A evidence.
  A one-token prefill probe's tiny decode interval is excluded from decode tokens/s.
  Followup therefore prioritizes failure diagnosis for the retained failed screen.
- Builder status/cancel/result now reject same-task non-build attempts, preserving
  the capability's attempt-kind boundary through the composed entrypoints.
- Agent instructions prefer a relevant complete job package, permit multiple CCs
  where useful, and retain narrow packages as optional compatibility surfaces.

## Validation and limits

Focused tests exercise real CC Host entrypoints and SQLite evidence across a
whole job without alternating package IDs. Prefill tests also drive select,
execute replay, collect, followup and stop with an explicitly simulated runtime.
Source-integration tests use real scope/grant refusals plus a simulated API process
for build/lab request/output contracts. No compiler, GPU model or new live-agent
experiment is run by these tests. The preceding real rejected screen remains
historical evidence for the previous package versions, not a live proof of this revision.

An additional operator-driven native workflow used only `factory.inference_lab`
on the saved real screen: query, read, diagnose, test_scope, followup and publish.
It recognized 14 requests and the explicit correctness failure, excluded artificial
one-token decode throughput, saved `diagnose_failure` as the proposed next input,
and created zero attempts. This is real CC execution on retained real data, not
a new live-agent or model experiment. The receipt is
`results/job-package-retained-analysis.json` in the Spark workspace.

The full factory suite passed: **810 passed, 1 skipped**. Package sealing covered
31 declarations. No global dependencies, model files,
shared Docker state, scoring contracts or historical handoff archives are changed.
The standalone deployed image is not rebuilt by this source/package revision;
the normal image-refresh workflow imports the new shared module on its next build.
