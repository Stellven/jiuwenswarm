# CC packages and an agent-driven Strata improvement loop

This iteration follows the current Muxite CCv2 package design, pinned at
`e897ff47a89a2f0e07db1e63b399d45abf0cc02e`. See
[alignment and source receipts](CC-PACKAGE-VERIFICATION-ALIGNMENT.md).
The objective is a useful factory/lab loop, not an optimized CC implementation or
an automatic claim that every attempted engine change is better.

## Implemented packages

| Package | Capabilities | Evidence boundary |
|---|---|---|
| `factory.inference_lab` | test_scope, diagnose, propose, ablation, cache_protocol, followup, profile_plan, analyze_profile, evaluate_prediction | Methods/advice and scoped evidence analysis; no GPU launch or grants |
| `engine.strata_prefill_workbench` | inspect, design, apply, verify_profile, submit, status, result | Native full-six Strata configuration and prefill subsystem experiments |
| `factory.cc_qualification` | inspect_package, verify_unit, assess_admission | Sealed package plus local implementation identity; independent bounded configuration invariants |
| `factory.engine_factory_loop` | status, select, execute, collect, stop | Admitted templates, durable decisions and child attempts; no host hypothesis chooser |

The methodology package groups existing tools as well as new scope selection.
This is not nine newly implemented optimization algorithms. Existing narrower CCs
remain available. Package materials carry methods, scope definitions and explicit
verification units; no mandatory CC core schema fields or registry were added.
The first domain qualifier supports the workbench's profile transformation unit.
It does not automatically certify every imported package or sibling capability.

## One concrete workflow

1. The agent receives a hardware/model-specific contract and reads retained reports.
   It uses `inference_lab.test_scope` to choose a subsystem test for a prefill claim.
2. It inspects the workbench and applies one change: chunk256 to chunk512. It saves
   the input/output pair. `cc_qualification.verify_unit` independently checks the
   exact changed field, six experts, no drafting, fixed environment and resources.
   `assess_admission` checks the task's selected capability policy. Source/module,
   API and checker hashes accompany the package release and saved evidence.
3. It chooses an admitted screen through `engine_factory_loop.select/execute`.
   Selection revalidates required qualification rather than trusting an observation
   that simply says eligible. The agent ends its turn after durable submission.
4. The supervisor confirms that the entire control container has stopped. The host
   recorder runs the engine with the model mounted read-only and a GPU lease,
   resource guards, deadline, journal and cleanup. No factory build runs concurrently.
5. A fresh real JiuwenSwarm session collects the result. The agent chooses whether
   to spend its second experiment on independent ABBA confirmation. The host does
   not make that scientific decision or prepopulate it.
6. It reviews the confirmation, publishes a scoped decision and proposes the next
   input. A null result or crash is retained. Acceptance revalidates original raw
   evidence through the host and matches the ledger child to the exact template.

The live task is `spark-agent-improvement-001`. Operator preparation is separately
recorded as `spark-agent-improvement-inputs-001`; preparation receipts are not
agent execution. Raw mission results and decisions are recorded separately below.

## Experiment contract and interpretation

Both arms use the same immutable Strata image and existing DeepSeek pack. The
model files exceed Spark physical memory. Only native prefill chunk changes.
Screen order is AB; confirmation is ABBA. Each fresh process repeats one pinned
512-token prompt seven times, discards four warmups from the primary metric, and
measures three requests producing one token each. All positions remain retained.
Drafting, prefix reuse and adaptive expert caching are off; all six experts run.

Primary metric: median native prefill milliseconds per process. Confirmation
requires at least 5% ratio improvement, both candidate process medians below both
baseline medians, exact single-token agreement across every request, and verified
raw protocol/configuration/cleanup/resource evidence. This is a small-N scoped
signal. It is not a full-generation quality result, decode tokens/s, TTFT result,
statistical proof of broad generalization, or authority to promote defaults.
Historical ARC/main experiments retain their own distinct contracts and outcomes.

## Factory limitations and next useful capabilities

The loop currently chooses among exact admitted templates. It does not autonomously
admit new source patches, install paper-derived implementations, search all Strata
layers, or establish weeks of unattended reliability. Those are future extensions,
not hidden results of the present run. The host boundaries should remain while
expanding the agent's toolbox and the admitted experiment envelope.

Useful next packages are expert-routing trace capture and readiness validation;
causal prediction/replay with wasted-read and stall costs; CPU versus GPU expert
placement cost measurement; kernel microbenchmarks and numerical checks; and
instrumentation failure triage. MoE-Infinity and Fiddler motivate questions and
methods, not expected Spark speedups. Live expert-trace emission and a measured
prediction intervention remain missing. The existing DS4_PROF crash is unresolved
and must not be erased by a successful uninstrumented test.

For longer campaigns, add source-derived package intake with pinned provenance,
meaningful domain verification units, reviewable capability admission, and novel
bounded templates. Add fault/reboot recovery qualification, storage quotas and
retention policy, experiment deduplication, and held-out integration confirmation.
The useful loop is evidence -> hypothesis -> cheapest discriminating test ->
retained result -> revised hypothesis, with integration tests when the claim grows.
It should retain negative results and avoid spending every cycle on a full model
benchmark. Automatic recursive optimization of CCs is outside this work.

## Validation and live evidence

The real JiuwenSwarm run used GPT-6.1 Sol and completed in 362.73 seconds across
two control generations. It made 47 native CC calls across 19 capabilities. The
agent chose screen `prefill-screen-001`, submitted child
`spark-agent-improvement-001-loop-1` / attempt `4450fa8a398240f5b03df005f967202d`,
ended its turn, resumed, collected the original result and made a new decision.
The engine experiment took 174.40 seconds including setup/quiet waiting. Both
fresh-process cells completed, passed raw-evidence verification and cleaned up.
Both control containers exited with code0, Running=false and Pid=0. Only the two
pre-existing unrelated containers remained running after completion.

| Screen observation | Baseline chunk256 | Candidate chunk512 |
|---|---:|---:|
| Measured median native prefill | 4368.7ms | 3211.6ms |
| First request prefill, excluded warmup | 17112.6ms | 13495.9ms |
| First output token, all seven requests | 9544 (`Here`) | 5 (`#`) |
| Effective experts | 6 | 6 |

The descriptive A/B timing ratio was1.3603, but **cross-arm correctness failed**.
The agent did not execute confirmation and did not promote chunk512. Its second
decision was `report_inconclusive`, explicitly retaining the runtime mismatch
rather than letting passed configuration qualification override it. It stopped
the loop and proposed a separately admitted diagnostic A/A campaign before
scoring further performance. Within-process repeatability held in both arms;
fresh-process repeatability and the cause of cross-chunk divergence remain open.

This does not establish that token9544 is a semantic ground truth or prove an
engine defect. Numerical reduction differences, routing changes and implementation
errors are hypotheses. A useful next CC package is numerical parity: deterministic
token replay, top-logit/margin comparison, first-divergent-layer capture, and
kernel-level numerical checks against a trusted reference. It needs actual engine
instrumentation and verification units before admission. That package is proposed,
not implemented. Historical ARC results are not rescored by this narrow test.

Six failed native receipts were retained: one diagnosis input, two malformed
observation publications, one selection input, an excessive query limit and an
unauthorized direct child query. The agent repaired the input errors and used the
parent's retained result rather than widening scope. These point to documentation
and typed-input ergonomics improvements. The run demonstrates bounded recovery,
not that tool errors have been eliminated or weeks-long operation is qualified.

Evidence under `/home/user2/software-factory-spark-20261113`:

- `results/agent-improvement-proof.json`: selected actual calls, receipts, decisions,
  qualification identities, worker source hashes, raw result and stopped-control proof.
- `results/agent-improvement-mission.log`: terminal supervisor outcome.
- `agent-improvement-v1/`: exact templates, role image receipt, operator preparation
  receipts, source snapshots, preparation/launch/proof scripts.
- `exports/cc-package-loop-v1/`: separately verified exports for operator inputs,
  real agent parent and measured child. Original raw data remains in the mission store.
- `results/cc-package-loop-final-tests.log`: **783 passed,1 skipped** in90.17s.
  Earlier full-suite formatting failure and its59-test recheck are also retained.

The new agent image is
`sha256:8923ae85eb0aa37d90d4ca44b0516be9ec98de8f98d70858bbbc1099f6d7b80b`.
Its standalone smoke imported the actual Jiuwen facade and sealed23 packages.
The real mission additionally used the supervisor's read-only `/factory` source
bind. Runtime Strata image and model files were reused; no global dependency,
model, driver, engine-source or runtime-image changes were introduced.

