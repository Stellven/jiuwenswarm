# CC-v2 revision from factory use (F25)

Compared against the read-only `~/tools` repository:
`main` at `89893083ebbcb3b54f5672df720e3afc37a8df7e`, its CC Protocols
README, USAGE, FORMAT, IMPLEMENTATION and `reference/ccv2.py`, plus
`origin/ccv2-runner-fixes` at `ea057c1cdf413e124ec480005c0376e3f3f2015f`.

## Existing implementation versus reference

- Same lightweight declarations, portable release identity, native/image/delegate
  bindings, durable keyed receipts, artifacts, service lifecycle and source builds.
- JiuwenSwarm uses package-relative imports and adds the eight-tool `agent_mcp`
  catalog, workspace handles, multiple roots and duplicate-ID protection.
- The reference fixes already exist: snapshot Git, Docker helpers and Docker
  removal detach stdin; finite image calls use `--pull=never`, as services do.
  F25 also detaches source-materializer helper stdin from the MCP protocol pipe.
- Ease-of-use defaults already match: semantic assessment is opt-in; advertised
  guarantees do not run checkers. Advisory failure/unavailability preserves outputs
  and execution success. Explicit required checks gate acceptance; unavailable
  required checkers block dispatch. No new verification subsystem was needed.
- `608656eb` added optional material `kind` (component/skill/method/reference),
  capability `kind: tool`, parser/schema validation and catalog summaries.
  These local additions remain; schemas were not replaced with reference copies.

## Friction observed in factory use and minimal fixes

- Native preparation resolved the venv Python symlink to the base interpreter,
  which lacked the venv packages. `configure_agent` worked around this with
  `FACTORY_PYTHON` in capsule wrappers. `Host(python=...)` already existed;
  F25 adds `CCV2_PYTHON` (explicit argument wins, default remains `sys.executable`)
  and preserves the absolute launch path for `{python}`, including venv symlinks.
  The executable hash and changed-environment checks remain enforced.
  Factory configuration passes the controller venv through `CCV2_PYTHON` and
  retains `FACTORY_PYTHON` for old wrappers. No run.py edits are necessary.
- Nested components previously required a second `--ccs` root. One root now
  discovers `*/cc.yaml` and `*/components/*/cc.yaml`: two capsule levels only,
  deterministic path order within operator root order, with repeated paths
  deduplicated. It does not recursively search payloads or component descendants.
  Factory configuration now supplies only its top-level capsule root.
- Long work must remain durable jobs: finite MCP calls must finish within the
  60–300 second tool deadline. Factory APIs submit/status/cancel/result through
  jobq; capsule wrappers bound API calls to 49 seconds. Submission is not success.
  F25 does not extend deadlines or move builds/GPU work into synchronous calls.

## Nine pre-existing failures

- Eight source-build failures were caused by Git 2.34.1 rejecting
  `git apply --allow-empty`. Empty patch bytes now mean rebuild the exact base;
  nonempty patches retain `--check --index --binary` and indexed application.
  Exact base/tree, source mutation, lock, LFS and failure-evidence checks remain.
  All eleven source-build tests pass in the sandbox after this change.
- `test_exited_launcher_does_not_confirm_children_stopped` used a sleep while
  its POSIX launcher could remain a zombie. The test now waits/reaps the owned
  launcher before asserting STOP_UNCONFIRMED and a live orphan. Cleanup tolerates
  an already killed zombie when container PID 1 does not reap it; it still checks
  that status explicitly. Production stop/reconciliation checks are unchanged.

## Deliberately outside this revision

No registry, planner, intent compiler, new lifecycle/verification subsystem,
automatic dependency installation, provider expansion or M1 restoration.
No Docker/GPU execution, compilation, live-agent run, commit or deployment.
Service, MCP and full-suite results must be distinguished from focused tests;
the operator must rerun integration tests if the sandbox blocks sockets/stdio.

## Local verification

Factory: before and after, 289 passed / 1 skipped. Source builds: before,
3 passed / 8 failed; after, 11 passed. The launcher regression now passes.
The venv and bounded-discovery regressions pass. Without MCP stdio tests,
CC-v2 reports 92 passed / 1 skipped / 10 failed / 2 errors: socket creation
is denied by the sandbox. No checks were skipped to hide those restrictions.
The full suite stalled in its first MCP stdio test and was stopped by the
300-second timeout (exit 124); the operator must rerun it outside the sandbox.
