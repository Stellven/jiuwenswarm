# Agent-directed construction and execution identities

The factory retains its Controller, Store, taskgraph, Builder, Jobs, Manager and
mission supervisor. An experiment is an evidence-producing intervention, not
necessarily a tokens/s benchmark. CPU negative controls and failed diagnostics are
retained. The independent engine acceptance policy is never supplied by a probe.

## Packages and identities

The 48 existing factory declarations have new patch versions and passive
`roles.json` materials. `ccs/migration.json` maps historical releases to canonical
releases. `Host(..., legacy=True)` explicitly loads historical local kind fields;
the default parser rejects those fields. Historical manifests are not translated
or rewritten. The separate baseline CC increases the declaration count to 49.
Discovery and component loading read roles from sealed material bytes. Ordinary
semantic verification remains opt-in.

`execution_binding.create` constructs factory provenance containing the sealed
package release, backend file manifest, interpreter/dependency or runtime image
identities, and selected sealed component artifacts. API dispatch and authored lab
workers verify the backend before executing. Build requests also retain source and
dependency commits/trees, toolchain and recipe hashes, target and flags. Equivalent
read-only container mount aliases may use the same file manifest; changed bytes
require another binding. Runtime component selection cannot fall back to a current
checkout when a task has selected sealed components.

Bindings are operator admission data in `constraints.execution_binding`; they are
not an added CC protocol field. Native trusted-local wrappers are not a sandbox.
The controller and diagnostic containers retain their separate existing authority.

## Prepare, select, build and collect

An operator `constraints.factory_loop.experiment_authority` declares `images`,
`purposes`, `permitted_changes`, `limits`, `acceptance_policy_sha256`, optional pinned
`model` (`path`, `sha256`), `owned_worktrees`, `max_build_attempts`, and
`max_gpu_launches`. Existing pinned templates continue to work. Empty templates
are allowed only when experiment authority exists.

`prepare_experiment(experiment_id, specification, image)` validates and freezes
without executing the experiment. The specification contains:

- `hypothesis`, `evidence_ids`, `purpose`, `changed_variables`;
- `artifacts`: a map of plain filenames to bounded text, mounted read-only at `/probe`;
- `recipe`: an argv array, with no implicit host shell;
- `measurements`, `interpretation`, and `budget`;
- optional `build`: an existing Builder request naming a clean owned source commit,
  a pinned dependency and `build_target` (default `strata-dsv41`).

Purposes are `cpu_analysis`, `gpu_probe`, `engine_diagnostic`, and
`engine_comparison`. The generic authored path remains diagnostic/nonpromoting;
scored comparisons continue through independently checked benchmark templates.
Budget fields are positive integers `timeout_s`, `cpus`, `memory_bytes`,
`output_bytes`, and `pids`, each bounded by the operator envelope. Native builds use
the existing eight-CPU/16-GiB isolated builder profile and their separate bounded
build deadline. No model mount is supplied to the builder.

Select exactly one `template_id` or `experiment_id`. For prepared experiments,
`hypothesis_id` is the frozen hypothesis text and evidence IDs must match. Existing
branch readiness and graph/decision revision checks still apply. Selection reserves
a durable cycle before dispatch. A source/probe build is a separate durable job;
execute returns its pending state until success. Manager admission and a checksum
of the actual packaged executable must pass before the lab job is submitted.
Committed source/dependency trees are extracted before compilation, so subsequent
worktree edits cannot alter the compiled source. Produced images receive permanent
content-identity retention tags in addition to requested convenience tags.

The agent ends its turn after submission. The existing supervisor proves control
has stopped before releasing a quiet receipt. The lab job uses no Docker socket,
network, credentials, writable model mount or arbitrary host mount. Output tmpfs
and combined stdout/stderr are bounded; timeout, OOM, nonzero exits, partial files
and exact-owner cleanup remain evidence. Build phase output is also bounded.

Collect copies verified child artifacts into parent-scoped evidence so the agent
can inspect raw results without widening cross-task reads. Retry the same cycle
and idempotency key after a lost acknowledgement. Never use a new ID to hide an
attempt. `abandon` refuses a cycle with a real build or lab attempt.

## Shared budgets and completion

`campaign_budget_owner` links task revisions to one operator budget. Jobs count
all related attempts, including failures, against the owner's limits. Controller
turns and elapsed wall time are also capped by the owner. Recommendations use
remaining resources and explicit cost estimates, exposing missing estimates and
keeping future proposals separate from executable authority.

A report observation is not completion. A terminal decision needs evidence and no
active, unknown or uncollected work. The controller can cancel an otherwise idle
stream after such a decision and then close transport. Cached usage details are
retained when the provider reports them.

The bridge's explicit `--drop-first-gpu-ack` option is a bounded recovery exercise:
it retains and withholds one already-submitted GPU acknowledgement for 75 seconds.
Its durable record prevents a restarted bridge from injecting another loss. It
never resubmits the underlying work or creates additional allowance.

## Baseline scope

`engine.performance_baseline` bundles inspection/accounting, page replay, ceiling
analysis, experiment generation, methodology, integration skill, verification units
and native/Python oracle sources. Actual GGUF headers are read with bounded parsing.
Unsupported packed formats remain gaps. The native oracle currently supports real
FP32 row-major tensor slices with deterministic calibration inputs, CUDA/cuBLAS
matvec, FP64 CPU reference checks, copy-bandwidth and empty-launch calibration.
Its result is a resident slice measurement, never measured whole-model tokens/s.
The Python variant additionally requires an admitted runtime with PyTorch.

Reports separate measured Strata baseline, ideal expert-availability reference and
capacity-constrained reference. Missing engine measurements and quantized expert
kernels remain explicit. The Roofline calculation uses compute, traffic and
dependency bounds with matched precision/sparsity. Fixed-page farthest-next-use
replay reports capacity, reads and readiness for a serial modeled schedule; it is
not a proof of global optimality. See the [NERSC methodology](https://docs.nersc.gov/tools/performance/roofline/).

Acceptance evidence, resource expenditure, historical failures and restoration
checks are recorded separately from these implementation contracts. Do not infer
end-to-end engine improvements or weeks-long qualification from bounded probes.

Bound build/lab workers set `PYTHONSAFEPATH=1` and the frozen runtime's
`PYTHONPATH`: a queue working directory cannot shadow the admitted backend.
Build fingerprints include the execution-binding ID. A failed build closes its
cycle and writes the failure observation in one transaction; it consumes the
attempt allowance and cannot silently become an abandoned reservation.
