# One package for a bounded source integration job

This mixed package supplies integration skills and native tools together. Use
`factory.integration_skill` for generic source work or `engine.expert_streaming`
for its eight historical llama.cpp components. Either package supports the
complete evidence, inspection, build and lab lifecycle below; opening both,
plus builder and lab_client, is unnecessary. Independent jobs may use independent
packages. Tools share the existing task-scoped backend and grant checks; a
package does not grant execution authority or apply source changes.

1. Use evidence_query/read and inspect against the host-bound workspace handle.
   Establish the actual repository, revision, dirty state, engine target,
   hardware and immutable contract before selecting a component. inspect_strata
   reads the pinned Strata inventory; it neither imports historical patches nor
   certifies that an unbound source tree is buildable.
2. Read INTEGRATE.md and the selected component materials. Publish the decision
   with evidence_publish before a bounded next action. Integrate only into the
   authorized checkout after compatibility and patch checks; this package never
   applies patches, imports a reference tree, or commits source automatically.
   A historical source path needs a host-bound clean checkout at the required
   revision. Missing or dirty source is a blocker, not permission to reset it.
3. build_submit acknowledges a durable attempt, not a completed build. End the
   turn, then read build_status and build_result in later calls. Do not infer
   success from a queued receipt. Use a fresh idempotency key for changed inputs;
   retain rejected attempts. build_cancel cancels only owned build attempts.
4. Read PREFLIGHT.md. Check exact image identity, argv and effective settings
   with preflight/verify_effective_config only where their llama-compatible
   probes apply. They need gpu.use even for the CPU model probe because it uses
   the NVIDIA runtime. Unsupported engines need their own verified target probe;
   a generic package does not make a llama probe valid for Strata.
5. lab_submit runs the frozen contract on one admitted build image. An image
   object is exactly {tag, id}; build_attempt_id is a separate input. lab_ab_submit
   queues one component-bound ABBA comparison; its base_image/candidate_image
   objects also carry build_attempt_id. The A/B backend uses the task's contract
   and registered component materials. It does not accept arbitrary new Strata
   patches or a changed scoring contract. If the target lacks this adapter,
   publish the missing capability rather than routing it as historical llama.
   End the agent turn after durable lab submission so the supervisor can stop
   control before quiet measurement. Do not poll/sleep inside a model turn.
6. Read lab_status/lab_result or lab_ab_status/lab_ab_result in later bounded
   calls. lab_cancel handles both ordinary and A/B owned lab attempts. Never
   overlap builds and GPU evaluations. Submission tools require process.exec
   and gpu.use; cancellation/result calls retain task and attempt ownership
   checks. A successful receipt says the call completed; inspect attempt state,
   execution_outcome, correctness and evidence before claiming a result.
7. Follow REPAIR.md to revise the decision, preserve failed evidence and stop
   when budget, authority, compatibility or evidence is insufficient.

For A/B work, freeze model/prompt/greedy/context/offload and the bare reference.
Change one treatment, use untraced complete ABBA rounds, compare exact output
hashes and per-arm engagement, and inspect the backend's acceptance verdict.
Tracing is explanatory evidence only. Observability needs bounded overhead and
signal capture, not a speed claim. Missing measurements remain unavailable;
never multiply successive component ratios or relabel null evidence as a win.

Canonical integration materials live in integration_skill/{JOB,INTEGRATE,
PREFLIGHT,REPAIR}.md. expert_streaming carries identical bundled copies so its
release is self-contained; packaging tests enforce copy equality. Update the
canonical files and copy them together when revising these skills.

expert_streaming also bundles AB.md from methodology_ab/AB.md for the full
llama-component acceptance procedure. Its lab_client.* names correspond to this
package's lab_* aliases; no separate lab_client package is required.
