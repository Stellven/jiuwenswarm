# Integrate into the identified engine target

Read JOB.md first. The source checkout, component base and task contract must
refer to the same engine and revision. The expert_streaming components are
historical llama.cpp changes based on cf34d3113. They are not Strata
optimizations and must never be applied to Strata by analogy. No build, patch,
commit, reference-tree import or GPU run occurs simply by opening this package.

1. Query/read current task evidence and the decision revision. Read the selected
   component manifest, ordered patches, hashes, base commit and dependencies.
   Inspect the host-bound workspace handle and repository-relative subpath.
   Work only in the authorized owned checkout, preserving unrelated changes.
   A recorded path or historical engine tree alone is not a usable source
   binding: require the expected revision and a clean checkout before building.
2. Verify each patch SHA-256 and dependency in order. For a compatible patch,
   first run git apply --reverse --check PATCH. A successful reverse check means
   already applied: record it and never apply twice. Otherwise run the forward
   --check before any explicitly authorized application. A failed check is
   rejection evidence, never a reason to force a patch or reset the checkout.
   Legacy factory.engine_component's e14b87603 base already contains combined
   patches 01..08; that special history does not apply to every engine.
3. Review the exact diff and publish check output, hashes and source identity.
   Commit only with operator authorization, retaining the component manifest as
   evidence. This guide and its tools do not authorize commits. If the builder
   requires committed clean source and that prerequisite is unavailable, publish
   the pending diff and blocker; do not submit an invalid or guessed source.
4. inspect reports source, host and optional image evidence; read its artifacts.
   Check the actual worker toolchain/PATH, architecture and base digest. The
   target may be DGX Spark, Jetson Orin or another supported engine adapter;
   choose only the operator-authorized target. Do not copy an old jetson-orin
   request or llama image tag into a Strata job.
5. Publish the decision, then build_submit with the existing builder request
   schema, exact source.path/source.commit, explicit target, unique output
   identity, environment and deadline. Read build_status/build_result separately.
   Build identity includes commit, patch stack, toolchain, digest-pinned base
   and build record/archive SHA. A mutable tag or binary hash alone is not
   equivalence. Preserve failed builds and use fresh identities for retries.
6. Preflight the admitted image and exact workload using target-compatible
   probes. Runtime engagement, correctness and performance each need evidence
   beyond build success. Keep generated staging, archives and build output out
   of source control. Revert only an authorized component change when rejected,
   preserve evidence and restore the recorded current best.

Builds and scored GPU work must not overlap. No push/deploy, clock, power,
driver, root-permission or baseline changes are part of this procedure.
