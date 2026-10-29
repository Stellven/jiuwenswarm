# Delivery status and verification extent

Recorded October 23, 2026. This is an implementation handoff, not an integrated
M1 acceptance report or a measured research result.

## Delivered to `ai4r_M1`

Remote `ai4r_M1` was checked at **`6a703050b8ea56e953c308298af37bf9fe6b1423`**.
It includes `e296d2b` (repository-owned deployment workflow) and `6a70305`
(no-sudo existing-image launch). See [operations](OPERATIONS.md).

| Area | Implemented behavior | Verification extent |
|---|---|---|
| Simple launch | `up` sets up owned state, pins existing app/runner images, stages supplied cases/inputs and starts the app; no implicit build/pull | Host/CLI tests and actual Compose rendering; live container launch not performed |
| Local development | Same CLI; ordinary Docker build/load images; relative local paths, default-user WSL, localhost 5175, generated Compose path for Docker inspection | Windows checks and Linux/WSL checks |
| Spark/SSH | Workstation builds/stages ARM64 images and selected inputs; SSH helper transport, image archives, logs and verified result retrieval; no registry or remote source checkout | Transport construction, transfer/recovery and hash tests; actual SSH/Docker deployment and Spark not exercised |
| Runner integration | Existing authenticated sequential queue through the separate `benchmark-runner` container; outputs persisted and fetched into a fresh directory | Fixture/API, filesystem, recovery and export checks; no authenticated full campaign |
| Lifecycle/storage | Repeat setup preserves state; owned cleanup, seven-day temporary TTL, protected results/inputs/credentials/models, logs bounded, 20% filesystem headroom checks | Local ownership/expiry/capacity tests; no target-host disk or unattended timer acceptance |

Normal launch invokes no sudo, forces no WSL root login and performs no host
cgroup preparation or service installation. It adds neither a privileged
container nor a Docker socket mount. Existing broker identities inside the app
image remain. Human model authentication and runner credential issuance remain
explicit; no credentials are stored in reports.

**Important limit:** removing host preparation makes app/container startup
simpler. It does not implement a new no-admin code executor. The existing
read-only app path can operate without delegated executor cgroups. Tasks needing
sandboxed code/scientific execution retain their actual prerequisites and can
return blocked results. Do not describe this as all tasks running on Spark.

## Separate committed features

| Feature | Branch / commit | Integration state |
|---|---|---|
| Required core typed Planner | `m1/required-typed-planner`, `9d8f21b140119ccec05f1a4f3cd5fa302cc01df5` | Local, committed, portable bundle supplied; not merged into or pushed with current `ai4r_M1` |
| Generalist | `capsules/generalist-m1`, `fe34b360322d38bdf6adb9744d4f16138925c277` | Optional candidate; not installed/admitted/activated by the deployment update |
| Table normalization | `capsules/table-normalize-m1`, `53e63011382e15dfc4d02a4532592b56cdd8e647` | Optional candidate, same boundary |
| Basic calculation | `capsules/calculate-m1`, `3a538f49072de3bb544a2064f039a1820414e499` | Optional candidate, same boundary |
| Markdown report assembly | `capsules/markdown-report-m1`, `69bc0937b5729c2eeac5d85720b73d953076ad75` | Optional candidate, same boundary |
| Capsule development/factory guide | `capsules/development-guide`, `aaf0fe8102d989902842916778ff86c4bc15a473` | Documentation on a separate local branch; earlier optional-Planner framing is superseded by the required-core feature |

The Planner feature supplies complete frozen admitted declarations, typed DAG
assembly, one bounded correction using deterministic diagnostics, retained
attempts, independent checks, semantic review, protected gates and Binder freeze.
It supports generic graphs while retaining scientific release obligations.
Its benchmark cases can explicitly select planned execution. Those new behaviors
are **not present merely because the deployment branch was pushed**. That feature
was based on `e296d2b`; combined integration with `6a70305` remains to be reviewed
and checked. Historical capsule/integration branches and bundles are preserved.

## Checks and remaining work

- Latest deployment revision: **31 Windows tests pass; 30 Linux/WSL tests pass,
  one skipped because Compose is unavailable in that Linux environment**.
  Windows exercised actual Compose configuration rendering without a daemon.
- Planner feature: **109 selected Windows checks and 39 Linux checks pass**,
  using controlled model responses for host/runner/gate/freeze mechanics. These
  are separate runs/feature revisions, not one combined final-system test total.
- A stale trace test was corrected to current v2 deferred-export semantics; its
  production capture function was unchanged. A broader finite-run test could
  not pass without the pinned OpenJiuwen distribution in the isolated test env.
- The user reported a Docker ingest socket error. The latest direct engine probe
  could not connect to `dockerDesktopLinuxEngine`. This does not establish the
  precise cause. Live image builds, two-container campaigns, actual SSH target
  operation, native ARM64/Spark execution and authenticated model quality were
  not verified here. Protected production calibration is not replaced by tests.
- No CC quality gain, benchmark outcome, completed scientific experiment or
  integrated M1 acceptance is claimed. M2 durable VM labs, per-capsule containers,
  capsule factory automation, shared local inference and Nuwa-skill work are not
  implemented by this delivery.

Next: enable a working Docker engine, build/load the matching image pair, use
`up`, authenticate, run a small supplied campaign and inspect/export its real
artifacts. Separately qualify no-admin code-executor support and merge/test the
Planner and desired admitted capsules. Spark execution can then establish its
own hardware evidence; it is not required to complete the local software work.

## Later supervised integration candidate

The source branches listed below were combined locally in
`m1/reviewed-integration-20261023`; see
[supervised integration status](INTEGRATION-STATUS.md). Shared `ai4r_M1` later
advanced to `1fd17ab`, deliberately reverting deployment while M1 work continues.
The earlier delivered/pushed statements above describe their original checkpoints,
not current shared deployment contents. The combined candidate is preserved for
later reconciliation; it was not pushed, activated or accepted as complete M1.
