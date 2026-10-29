# Final M1 source integration — October 23, 2026

**October 26 reliability update:** [reproducible Docker checks](../../docs/capsules/reliability-reproduction.md)
record 215 selected passing tests, including 31 status/recovery cases and the
interrupted-child custody fix. The app was rebuilt; authenticated readiness and
existing completed-run status passed. This supersedes the old pending status-test
failure. Live isolated semantic quality, accepted Pi/timings and full scientific
acceptance remain separate and pending.

**October 25 update:** [current M1 Docker execution](../../docs/capsules/m1-local-process.md) supersedes the separate-Builder and nested-sandbox status below. All feature histories are merged into the integration line. The user selected ordinary jobs inside the app container for M1; OpenJiuwen owns agents and Codex supplies governed text completions. Current source checks and image startup are recorded separately from pending authenticated scientific acceptance. Earlier sections retain their original dates and scope.

Builder upgrade branch: `builder/bounded-build-test-20261023` now uses the native agent loop with protected development actions and a separately pinned Pi benchmark. See [scope, design amendment and verification](../../docs/capsules/agentic-builder.md). This candidate is not merged into `ai4r_M1` or live runtime-qualified. The earlier three-candidate implementation and its tests remain historical evidence.

The new upstream AI4R baseline `125dafc57437700dc32005f5e2403a0aa00a519f`
is combined with the reviewed deployment, required typed Planner, four optional
capsule candidates and capsule development guidance. The final integration branch
is `m1/final-integration-20261023`. This is source integration, not a deployment,
production checking-asset qualification or completed M1 runtime acceptance.

The original candidate and source branch commits remain preserved. See the
[earlier candidate record](../../docs/capsules/history/2026-10-23-supervised-integration-candidate.md)
for the original merge table and bounded review. The user's later instruction
explicitly authorizes merging after the new AI4R was supplied.

## Final reconciliation

- Preserved upstream Brief v3, target comparison arithmetic (factor and unit-aware
  offset), historical Brief v2 reads, output-specific assessment behavior, exact
  contract exports and safe retained-upload reuse.
- Retained the required catalog-driven typed Planner, one bounded pre-acceptance
  candidate correction, protected independent checking, gates and Binder freeze.
  The merged core Planner is a new immutable `m1-13` release. The PDF work release
  stays upstream `paper-m1-5`; its affected Planner is reauthored as `paper-m1-9`.
- Planner catalog input is bound from the exact admitted declaration instead of
  a hardcoded core name. This also supplies the required catalog to the retained
  legacy PDF Planner; both paths have a real Factory pre-dispatch regression.
- Both Compiler target-comparison checker closure and Planner graph-checker closure
  are preserved. Earlier optional `workflow.capability_planner` is not restored;
  new Library snapshots continue to mark its legacy identity non-selectable.
- Static remains the default plan source under design decision D39; planned
  execution is explicitly selected before a run. The incoming planned-default
  capture was not allowed to override that maintained design requirement.
- New local captures use `local-research-unified-v3` to avoid silently reusing an
  older captured configuration. Existing state, accepted plans and historical
  snapshots are not rewritten or automatically upgraded.
- Seven narrow Git EOL rules reproduce upstream CRLF-pinned declaration, prompt,
  Hypothesis and checker bytes on every platform. Other source stays LF under its
  existing rules. Upstream compiler/scientific/PDF work hashes were preserved;
  no hash guard was weakened to make validation pass.
- Corrected test fixtures for current release versions, Brief v3 input ports,
  protected actor scope, exact admitted rubric bytes and the full static-checker
  source closure. Historical fixture files remain intact.

Upstream replaced the paused line with a new history from `bfc30ba`. The pause
commit `1fd17ab` has exactly the same tree as that common base. Integration commit
`b0d05471` joins the new upstream and reviewed features. `20aaa94c` then records
that superseded pause ancestry using the already integrated tree unchanged. This
preserves both histories without replaying the old deployment removal. No force
update of the shared branch is needed.

## Verification extent

Fresh Windows checkout at code commit `07c7abdf`: **225 passed, 4 deselected,
3 subtests passed in 67.78 seconds**. This includes Compiler/Planner acceptance,
Brief v3 targets, pinned assets, capsule workers, source checks, deployment,
sequential runner and upload reuse. No new cases were excluded.

Fresh Windows source pins verified all 7 scientific, 3 paper and 4 optional
catalog entries. An independently materialized Linux source-subset checkout also
verified those exact catalogs and the Planner/PDF checker pins. The attempted
full-history clone of the local partial repository failed on a missing promisor
object and is not represented as a successful clone or Linux application run.

A separate shared-fixture regression run passed 26 checks and failed one
connected private-measurement case with `audit_unavailable`. Its XML is retained;
RSI/private execution is not claimed accepted. The three partial-output stop
cases pass after adapting the current-release input fixture to Brief v3.

The final additional Luna read-only review could not run because workspace
credits were exhausted. Earlier scoped Luna reviews completed; the supervisor
performed final source/conflict review and verification instead.

Exact commands, JUnit, logs and final refs are retained in the notebook's
`Resources/review-batches/2026-10-23-final-merge/` receipt. The previous 187 checks
and intermediate failures remain historical runs, not a combined final total.

The same four exclusions remain explicit: three connected scheduler cases need
qualification of their pinned native environment, and one existing Windows
routing-custody fixture fails before its expected qualification assertion. No
new cases were excluded to make the final merge pass. The custody guard remains.

A live authenticated campaign, genuinely dynamic generic DAG through real
execution and terminal delivery, scientific execution, actual SSH deployment,
ARM64/Spark and model quality are still unverified. No capsule was qualified,
admitted or activated merely by merging its code. RSI and model-router
implementation remain outside this work; their existing authority and frozen
contract boundaries are preserved.

## Next operational step

Use [the runbook](OPERATIONS.md) and explicit matching app/runner images. Existing
installations require a deliberate new configuration/release qualification;
source integration is not an automatic state migration. Run a small campaign,
retain exact source/image/plan and output/check/gate evidence, and inspect the
real results before claiming runtime acceptance. Optional capsule adoption
continues through independent checking-asset qualification and human activation.
