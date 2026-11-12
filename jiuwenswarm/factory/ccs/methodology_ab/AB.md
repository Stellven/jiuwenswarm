# Grow an engine with counterbalanced A/B evidence

Adapted from siminfeng c2/skills/engine-ab-experiment/SKILL.md and c2/METHODS.md;
cc/abrun/gate.py is the performance gate, not historical experiment numbers.

1. State the mechanism hypothesis, uncertainty, expected evidence, and scope
   before integrating. Read the component's dependencies and source patches.
   Change one component per experiment; keep every other workload variable fixed.
2. Record source commit, patch hashes, build receipt and immutable image IDs.
   Build the bare engine first. Current best starts there. Apply dependencies in
   order in the owned source.branch, with one integration commit per component.
   Dependencies are source requirements, not evidence of benefit: if a dependency
   was reverted, explicitly test its addition again or report the dependent blocked.
3. Fix the contract's model, prompt, seed, context, offload and greedy argv.
   The operator must freeze the bare contract reference before scoring.
   Candidate engagement checks belong to component.yaml, never to the contract.
4. Prefer env-only arms in one admitted image when that isolates the variable.
   Otherwise use the admitted current-best and candidate images. Keep the base
   environment at its recorded best settings; override only the treatment.
   Pass component ID to lab_client.ab_submit; the Manager selects checks.
   Each image input is {tag, id, build_attempt_id}; both require build admission.
5. Submit one complete ABBA experiment through lab_client.ab_submit with
   base_image, candidate_image, base_env, candidate_env, rounds, component and
   idem_key. Contract comes from the task (optional explicit matching contract_id).
   The Manager queues one durable gpu job; the worker runs abrun without --submit.
   End the agent turn after submission. Read ab_status / ab_result next turn.
   No GPU/build/heavy CPU overlap. Inspect queue and external load evidence;
   contaminated timing is unscored, never a win.
6. Use printed eval_ms_per_token (lower is better), not rounded reciprocal t/s.
   ABBA provides repeated A/A and B/B observations; repeat complete rounds.
   Inspect all summaries, startup activation and exit counters, stdout hashes,
   telemetry, watchdog and REPORT.md. Success or an env string is not engagement.
   thread_names uses sampled xfill-* workers, has measure: none, and cannot
   establish a performance improvement on its own.
7. gate.py computes arithmetic arm means. For ms/token ratio is A/B.
   aa_gap is the largest within-arm (max-min)/mean. Drift is the absolute
   difference of the two base-half means divided by the whole base mean.
   threshold = max(0.03, 2 * aa_gap, 2 * (drift or 0.0)).
   Improvement requires ratio - 1 strictly above threshold; equality is null.
   Missing, nonpositive or nonfinite metrics, unsuccessful runs or activation
   mismatches invalidate scoring. Missing replication is not stability evidence.
8. Require output class identical AND every base stdout SHA equal to the frozen
   contract reference. Unknown or differing output is candidate_failed even if
   speed improves. Identical greedy stdout is this contract's obligation; it is
   not a general accuracy or numerical-equivalence claim.
9. Read ab_result: gate, ratio, aa_gap, output_class, per_arm_ms and evaluation.
   Read acceptance.type/verdict/reasons. Performance requires gate improved;
   observability requires every candidate engagement check passing, correctness
   pass, and overhead 1/ratio - 1 <= max(overhead_bound, gate threshold).
   thread_names is keepable on sampled signal plus bounded overhead; never claim
   a speed gain from it. Missing capture is not_measured and acceptance invalid.
   All keeps require valid complete evidence and correctness pass. Publish
   keep_component {component,image,ratio} citing ab_result acceptance.verdict
   accept and the evaluation. Otherwise revert with component and reason anytime,
   restore best env/image and retain the failed/null evidence.
   Exception, dormant prerequisite: if a rejected component's source is required
   by components not yet measured and its switch is off by default, you may keep
   its commit with the switch OFF in every later arm and publish keep_dormant
   {component,reason,needed_by}. Its own rejection still stands; dependents are
   measured against the current best with only their own switches on. If a
   dependent is later rejected too, revert both in reverse order.
10. Retain negative/null/invalid evidence and explain why. Finish with the best
    image, kept component stack, exact scope and evidence IDs. Budgets or missing
    prerequisites end inconclusively; they never imply a win.
11. To explain a result, not to score it, submit one lab_client.submit with
    run_config {"env": ..., "profile": "nsys"}. Nsight Systems traces the run;
    the evaluation carries details.nsys: top GPU kernels, CUDA API calls and
    OS-runtime calls (pread, futex, waits) with total times. Tracing slows the
    engine, so traced ms/token is never compared or cited as speed evidence.
    Use it to form the next hypothesis, then test that with an untraced A/B.

Never multiply successive component ratios. Final claim = direct bare-vs-final
ABBA if budget allows; otherwise explicitly state that comparison is not measured.
Settings trials: one knob, justified hypothesis, at most 3 trials per component.
Changing scoring rules requires a new contract id and a fresh reference.
