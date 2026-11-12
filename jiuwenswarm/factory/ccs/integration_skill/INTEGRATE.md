# Integrate an owned component

Adapted from siminfeng/c2/skills/engine-build/SKILL.md and c2/METHODS.md.
The old ref-tree/build-CC/jobq shell sequence is superseded here by the owned
agent checkout, factory inspector and asynchronous factory.builder capsules.
The host enforces authority; this material grants none. Commit only when the
operator has authorized committing; otherwise publish the pending diff and stop
before a builder request that requires clean committed source.

For the bare evolve task, use factory.components.<name> and methodology_ab.
Start at cf34d3113 on evolve; verify every ordered patch hash and dependency.
The e14b87603/combined-patch instructions in step 1 apply only to the legacy
factory.engine_component recorded demo. New components have ordered `patches`
and `depends_on`; apply/check each patch once in that order. Patch detection in
the legacy inspector describes patch 09, so record the complete evolving stack
and commit/patch identities separately as evidence. Revert only the component
commit when rejected, retain the evidence, and rebuild the current best.

1. Query/read current evidence and the decision revision. Read the component
   manifest, verify both copied patch hashes, base commit and combined-patch
   provenance. Work only in the owned checkout under FACTORY_WORKSPACE, never
   in siminfeng reference trees. Pre-integration e14b87603 already includes
   combined-01..08; never reapply it. Preserve unrelated changes.
2. Run git status and verify HEAD. For the candidate patch first run
   `git apply --reverse --check PATCH`. If it succeeds, record already applied
   and never apply twice. Otherwise run `git apply --check PATCH`, then apply
   once. A failed forward check is rejection evidence, not a reason to force.
   Publish the check output, patch SHA and diff as artifacts/observations.
3. Review the exact diff. When authorized, commit only the component change
   with a message citing the component SHA-256 from component.yaml (the patch
   sha256), retaining that manifest as evidence. Publish commit/tree identity.
4. Call factory.engine_inspector.inspect with source=the workspace handle and
   subpath=repository-relative path; supply the image when relevant. Read its
   observation and artifact. Require a clean source and the expected reverse
   patch detection. Check nvcc on the build worker's PATH, architecture and L4T.
5. Record the next decision and call factory.builder.submit with request and
   a fresh idem_key. Request source.path + source.commit, target jetson-orin,
   a unique factory/llamacpp tag and explicit deadline/environment. Submission
   acknowledges a queued attempt, never build success. Poll status/result in
   later bounded calls. Publish each transition/evidence reference. A retry
   uses a fresh attempt/output identity; never overwrite rejection evidence.
6. Build identity = commit + patch SHA + toolchain + base digest, together with
   build record/archive SHA. Distinguish local image Id from config/registry
   digest and tag. Binary hash alone is not build equivalence (METHODS D026).
   Preflight exact image/tool argv and effective config before lab submission.
   Runtime engagement and correctness are separate from build success.

Builds and scored GPU work must not overlap. Keep generated staging, archives
and live build output out of source control. No autonomous push/deploy, clock,
power, driver or root-permission changes are part of this procedure.
