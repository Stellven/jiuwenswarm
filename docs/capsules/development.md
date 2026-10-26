# Developing a capsule

A capsule is a versioned function with a declared contract, independently owned
checks and a controlled release. A successful task does not certify a reusable
capability. Build the smallest useful specialist; use Generalist for bounded
uncovered work and retain its low-trust provenance.

## The process

1. **Define the job.** Record inputs, exact output shape, resource/effect limits,
   failure behavior, what is explicitly unsupported, and a concrete public
   example. Decide whether the existing work-packet envelope fits. If stronger
   typed specialist ports are needed, author their schemas and an explicit
   adapter instead of silently claiming compatibility.
2. **Specify independent checking before the body.** Freeze expected behavior
   and negative cases: missing/malformed inputs, wrong values, source corruption,
   scope escape, misleading claims and uncertainty. Keep private evaluation
   cases out of worker context, application images and public examples. The
   worker may produce evidence; it cannot supply its own acceptance verdict.
3. **Create an isolated branch from the shared foundation.** Add one directory
   under `jiuwenswarm/research/capsule_extensions/<module>/`, containing
   `__init__.py`, `worker.py`, `checks.py` and `release.py`. Additional local
   helper modules are allowed. Do not edit other capsule packages or central
   startup lists. Optional discovery removes that shared merge bottleneck.
4. **Implement bounded work.** `async execute(ctx, inputs)` returns declared
   `ProducedArtifact` outputs. Use `ctx.model` for the existing audited model
   path and scoped artifact methods for allowed reads. Do not call a provider,
   shell or host filesystem outside its declared/enforced profile. Preserve
   original files, provenance and low-trust taint. Pure transformations need no
   model call, though M1 still budgets their independent semantic review.
5. **Prepare immutable assets.** `release.prepare(store)` returns declaration,
   body, check-bundle, semantic-profile and implementation references; expose
   `execute` and `check` from the module. The shared asset helper supports an
   explicit `version=` argument. Reuse it for simple packet tools; more specific
   schemas/declarations may require a dedicated preparation function. Change
   the release version whenever previously released bytes change.
6. **Freeze, test and review.** Run
   `python -m jiuwenswarm.research.capsule_extensions.release_tool <module> <namespace.name>`.
   This authors `release.json`; it never runs at startup. It pins all local
   Python files and shared packet/asset helpers. Review the complete release
   closure, including checker code, schemas, interpreter and dependencies.
   Add meaningful function tests and malformed/escape/taint negatives. Check
   actual registered bundle behavior, not only worker self-tests.
7. **Verify a fresh checkout and composition.** Candidate preparation must
   reproduce the same hashes on Windows and Linux. Check types, declared
   dependencies, coverage, budgets and gates in a real DAG. Test compatible
   reordering and repeated capsule instances where useful. A merge rehearsal
   should show capsule branches touching disjoint directories; keep shared
   policy changes in the foundation branch.
8. **Qualify, admit, activate.** Follow [the installation guide](capability-dag.md).
   Candidate preparation does not alter standing. An independent owner
   preregisters checking-asset cases and expected labels, runs protected
   calibration, inspects actual evidence, then uses the existing human Library
   operations. Missing credentials/evidence blocks qualification. Unit-test
   success, source merge and an agent's claim are not substitutes. Startup
   registers only the exact active admitted release.
9. **Run and retain evidence.** Exercise the ordinary app/benchmark runner after
   activation. Preserve frozen plan/declaration/image/source identities,
   original inputs/outputs, model/tool observations, checks, gates, failures and
   costs. Humans judge benchmark cases. Keep source-only checks distinct from
   model, Docker, ARM64 and Spark execution. A new release applies to new frozen
   plans; never mutate an active run or overwrite old evidence.

## The implemented examples

The optional packages are independent examples, not prerequisites for every
capsule: active releases `research.generalist m1-2`,
`utility.table_normalize m1-2`, `utility.calculate m1-2`, and
`utility.markdown_report m1-2` respectively provide a low-trust fallback,
explicit JSON/CSV normalization, decimal statistics, and escaped Markdown
rendering. Their v1 source files remain unchanged, and their original manifests
are archived under `capsule_extensions/history/v1/`. The v2 releases pin those
worker/check bytes as external dependencies and use corrected result-schema
check IDs, so each is admitted by the same Library gate as other capsules.

Generalist has a stable small declaration and a per-run frozen task contract.
Host checks authenticate its task projection and actual expression result
before semantic review. Fixed checking criteria assess task alignment; the
Planner supplies intention and known optional checks, never arbitrary judge
code or permission. No source fidelity or scientific truth is inferred from a
semantic PASS. Failure or indeterminacy of a required check stops advancement.

The current work-packet schema is a bounded interoperability envelope, not a
claim that every transformation accepts every packet. Operation-specific fields
must already be supplied; actual inputs are checked at execution. Arbitrary
scientific ports need explicit adapters. Generalist authoring code as file text
does not mean arbitrary Python execution is supported.

`utility.summary_to_packet` is one explicit adapter from the exact
`urn:ai4r:paper-summary:1.0.0` contract to the existing
`urn:ai4r:work-packet:1.0.0` envelope. It preserves all summary and source refs,
adds low-trust provenance, and has deterministic output checks. It does not
imply compatibility between other schema versions or certify the summary.

## Release and collaboration rules

Keep declaration, body, checking assets and their byte identities together.
Never refresh all catalogs merely to silence a mismatch. Understand which
closure changed, issue a new immutable version and requalify it. Shared-helper
changes require reviewing and re-freezing affected releases. Current manifests
are integrity receipts for trusted installed source, not signatures proving
authorship or a complete dependency SBOM. Git/lockfiles and the image identity
remain part of the reproducibility record.

Merge foundation first and selected feature branches in any order. Deployment
is independent. Do not make the coding agent's own tests the private acceptance
oracle. Do not copy private scripts, credentials, model weights or retained run
results into a release. Required workflow code belongs in the repository.

M1 currently ships capsule **modules inside the ai4r image**, plus the separate
benchmark-runner image. Per-capsule containers, factory automation, VM/lab
provisioning and automatic promotion remain future architecture, not hidden
prerequisites of these modules.
