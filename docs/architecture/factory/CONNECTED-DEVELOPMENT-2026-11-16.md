# Connected investigation development

This development builds on the prior measured engine results. It changes factory capability and diagnostic tooling; it does not assume a new engine speedup.

## Branches and experiments

`factory.engine_factory_loop.select` accepts paired `branch_id` and `expected_graph_rev`. Set `constraints.factory_loop.require_branch_binding=true` for a connected campaign. Selection requires a current-task ready branch, matching hypothesis ID, current graph revision and enough conservative GPU reservation for campaign_timeout_s +120 worker seconds. It commits the decision, running branch and existing cycle reservation atomically. The existing loop experiment budget is still authoritative; no second executor or budget exists.

The host cycle ledger binds branch, selection revision, hypothesis, decision, template hash, child task, attempt and result. Branch status exposes these as `experiment_cycles`; agent-authored observations cannot manufacture that linkage. Graph revisions remain separate from lifecycle updates. A successful lab execution is not scientific acceptance or a numeric Pareto score.

A fresh dispatch rechecks branch eligibility. A pruned branch cannot start new work; previously submitted work still reconciles after pruning/deadline, and its retained result remains visible. Collection completes an investigation and attaches its result without restoring a pruned branch. The agent can refine a completed investigation into a new branch. `abandon` closes only an unsubmitted reservation, retains its reason and consumes its budget; it refuses a real attempt even when submission acknowledgement was lost.

Offline verification uses real Store transactions and a fake external benchmark. A separate actual native Host select/abandon test exercises package transport and task scoping without launching a GPU. This is not yet a new live-agent branch-to-GPU result.

## Reusable campaigns

The former overnight CPU launcher now requires a fresh explicit campaign specification: identity, absolute deadline, objective, checkout reference, explicit evidence, relevant package subset and bounded CPU-only limits. Frozen runtime hashes pin actual source bytes, including uncommitted changes. Resume cannot renew a budget or widen the task. Historical missions remain immutable. See [CPU campaign contract](CPU-CAMPAIGN-SPEC.md).

The CPU launcher intentionally cannot admit a GPU experiment. Connected GPU tasks use the existing operator task/factory-loop template path and supervisor. The two entry paths now have reusable policy versus lifecycle responsibilities; there is no claim that the CPU specification is a general GPU campaign compiler.

## Scoped qualification

The historical v1 checker still means exactly chunk256→512. The new `strata.prefill_profile.v2` checker reads bounded sealed parameters for256→512/1024, independently proves one-field transformation, preserves fixed expert budget and checks full-six/no-drafting obligations. Its identity includes the relevant producer modules, checker and API. Fresh source requires fresh qualification. The proof is configuration-only, not output parity or engine benefit.

## Numerical investigation

The new numerical package separates replay design, retained-output divergence, common-history logit comparison and native DS4 capture interpretation. Data identity and treatment differences must be explicit. Full and partial logit evidence have different permitted conclusions; no output divergence is assigned a cause without supporting observations.

The retained generic Strata `generate` program and the actual `strata-dsv41 --serve` executable have different capture paths. The latter already provides DS4_SERVE_DUMP. Use source-qualified DS4 semantics, reject missing/truncated captures, and check shared history before comparing a selected row. An instrumented diagnostic is not an uninstrumented speed result. The earlier proposed missing-observer gap must be refined to a missing validated factory adapter, not a claim that Strata contains no logit capture facility.

## Remaining acceptance work

A connected live agent experiment with interruption, a measured agent-cost comparison, source-changing optimization integration and multi-cycle endurance are distinct acceptance milestones. Do not infer them from offline tests, a CPU-only mission or an image import. Each fresh model campaign needs its own explicit immutable inputs and execution bounds. No old deadline or lab allowance is renewed by these code changes.

## Actual GPU diagnostic and tool repairs

Four fresh model processes were used, with no compilation or other GPU workload alongside them. Runs001/002 completed baseline generation but rejected truncated logit files;002 retained880,640 actual bytes versus25,856,000 expected. The recorder gives `/tmp`64MiB, also used during CUDA startup. A bounded FIFO-to-RAM transport then captured all50rows without increasing the recorder's memory/tmpfs allowance. Run003 reported only225,280bytes free in `/tmp` afterward, supporting temporary-space pressure as the explanation; no file-content correctness claim was made from the rejected dumps.

Run003 retained a complete baseline capture but import rejected the exec gate due to an adapter/test mistake: the actual recorder sends ASCII FACTORY_EXEC followed by byte10, not literal backslash-n. The corrected importer checks the actual recorder byte constant, rejects extra gates/requests, and re-imports retained data. Baseline generation was not repeated for this CPU parser correction. Run004 captured the candidate arm. Failed attempts and original frozen packages remain unchanged.

Actual Host calls imported both captures, checked their exact common49-token history and compared129,280 vocabulary logits at output index49. Baseline chose token10367 over32187 with margin0.0573387; candidate reversed that order with margin0.3701553. Maximum absolute full-vector difference was1.2083893, and each captured argmax matches its native emitted token. This establishes a same-history numerical difference at the observed output boundary. It does not locate the first differing layer, establish harmless rounding, measure quality noninferiority or authorize promotion. The generic comparison tool deliberately does not authenticate caller-supplied engine identities; the operator analyzer separately retains image/source/asset, recorder and manifest witnesses.

No new speed result is claimed: these captures synchronize/copy logits and drain a pipe. A matched observer-off/on timing experiment remains needed. No native engine source patch was required. The numerical CC now packages both the useful diagnostic and its failure/transport methodology.

Raw campaigns: ROOT/development-numerical-gpu-001 through004. Re-import and comparison: ROOT/development-numerical-analysis-001. ROOT is `/home/user2/software-factory-spark-20261113`. Reproducers are `tools/run_ds4_numerical_diagnostic.py` and `tools/analyze_ds4_numerical_capture.py`; they require fresh outputs and retain prior failure identities.

## Fresh live-agent run and cost

`development-cpu-mission-001` used the actual JiuwenSwarm facade with gpt-6.1-sol at max reasoning, five selected packages, a two-turn/300-second active CPU limit and zero GPU/build/experiment authority. It created one justified branch, applied the numerical first-divergence tool, indexed/projected evidence, attached findings and published an immutable final report. There was no forced branching quota. The controller then hit its 300-second timeout: this is a retained useful report, **not a successfully completed agent turn**. Cleanup removed the authentication symlink, exported evidence with no errors, and found no incomplete native receipts or receipt manifest errors. Two rejected native calls are retained alongside successful corrected calls.

Recorded usage was817,802 input tokens, of which745,856 were cached, and9,602 output tokens (3,200 reasoning tokens are included, not added again). This is a single cost observation, not a measured improvement over an equivalent mission. The next input proposal first audits existing captures and then proposes, without authorizing, a two-request observer-off screen. It explicitly leaves repeatability, observer overhead, quality and causal localization unresolved. The agent declined the generic followup tool's larger24-turn/four-hour proposal. RSI should improve that tool's budget-aware specificity, response size and evidence reuse; a bounded mission should publish and terminate promptly after its final report.

The exact agent report, next-input proposal and native receipts are retained in that mission directory. A subsequent CPU-only operator re-analysis in `development-numerical-analysis-002` additionally checked retained policy, replay-spec and wrapper bytes against manifests and reproduced the same common-history logit result. It did not spend another GPU run. Frozen mission inputs and earlier analyses were not rewritten.

## Final verification and portability

Final factory regression: **1,229 passed, one skipped in135.85seconds**, retained in ROOT/results/development-full-tests-final.log. These include real SQLite/Host transport checks and injected worker tests; they do not replace the missing connected live-agent GPU/endurance milestone. The CPU re-import additionally verifies the actual retained captures.

`deploy/spark/package-connected-development.py` exports an explicit source/evidence supplement with a complete SHA256 file manifest and standalone verifier. It excludes model weights, credentials, dependency environments and live databases. The separate refreshed ARM64 agent image must pass actual-facade import and package sealing before export; image identity and archive verification live beside the handoff. Preserve the previous night-branches handoff. No global packages or shared-container changes were required. Only owned exported duplicates are candidates for optional cleanup after verification and RSI import.
