# Supervised M1 integration candidate — October 23, 2026

This is a local integration candidate on `m1/reviewed-integration-20261023`,
starting at `14a69a0`. It is not current shared M1, a deployment, production
qualification, or M1 acceptance. No candidate was pushed or automatically
admitted/activated by this review.

## Current shared branch matters

During review, shared/local `ai4r_M1` advanced to
`1fd17ab1254b6c1f62d9c24e457d0a4cb835fe8a`, deliberately reverting the deployment
changes while ongoing M1 work continues. Its commit message explicitly preserves
the deployment, capsule, Planner and reviewed integration branches for later.
This candidate preserves the earlier combined work; it does not undo that revert.
A merge-tree rehearsal against `1fd17ab` reports a modify/delete conflict in
`deploy/m1/OPERATIONS.md`. A plain future merge must not silently discard or
restore deployment changes without reconciling that deliberate decision.

## Source combined here

| Input | Exact source | Disposition |
| --- | --- | --- |
| Existing deployment and documentation | `14a69a0` (includes `e296d2b`, `6a70305`) | Candidate base; now reverted on shared M1 |
| Required typed Planner | `9d8f21b140119ccec05f1a4f3cd5fa302cc01df5` | Merged locally; core `research.planner` |
| Generalist | `fe34b360322d38bdf6adb9744d4f16138925c277` | Candidate source merged; optional release |
| Table normalization | `53e63011382e15dfc4d02a4532592b56cdd8e647` | Candidate source merged; optional release |
| Calculation | `3a538f49072de3bb544a2064f039a1820414e499` | Candidate source merged; optional release |
| Markdown report | `69bc0937b5729c2eeac5d85720b73d953076ad75` | Candidate source merged; optional release |
| Development guide | `aaf0fe8102d989902842916778ff86c4bc15a473` | Merged; README add/add conflict resolved in favor of required core Planner plus capsule reading links |

Shared foundation `cb589aa` is inherited. The old optional
`workflow.capability_planner` implementation is not restored. Its historical
proposal remains explicitly historical. Merging code does not grant admission,
checking-asset qualification, activation, provider access, or execution authority.

## Review findings and corrections

- Required typed planning was absent from the earlier shared deployment revision:
  that policy accepted only summary or seven-stage scientific shapes. This
  candidate includes catalog-driven typed graphs and protected freeze.
- A persisted active old optional Planner row could remain selectable after its
  worker was removed. New Library snapshots now mark that identity non-selectable;
  standing and historical snapshots remain unchanged. The regression fixture
  models a legacy admission, rather than claiming an actual old production DB
  migration was exercised. Frozen historical runs are not upgraded or repaired.
- Static acceptance tests omitted three policy/checker files from the required
  implementation closure. The fixture now binds the complete four-file closure,
  retains swapped-source rejection and adds missing-file rejection. Scheduler
  stop tests now supply the required resource-read ceiling so they reach the
  actual stop check. Production acceptance rules were not relaxed.
- A fresh worktree created *before* merging the new `.gitattributes` retained
  unchanged CRLF files, causing seven integrity failures. Compared working bytes
  with Git blobs, refreshed only unchanged line-converted files to exact Git
  bytes, and retained the explicit legacy CRLF verifier exception. No declaration
  or release hash was changed to fit the failure. Fresh checkout at this
  candidate is preferred when integrating; verify release pins before building.
- One Luna reviewer initially called bounded Planner correction unauthorized.
  Supervisor checked the later user prompt and rejected that finding: one
  validation-guided candidate correction is explicitly authorized before final
  independent acceptance. Executed-node retries are a different boundary.

## Verification and remaining extent

Final combined Windows run: **187 passed, 4 deselected in 46.16 seconds**.
The exact command and JUnit receipt identify every selected file and exclusion.
This includes the legacy-selection fix and both corrected acceptance/stop fixtures.

The wider exploratory boundary run was interrupted after failures; it is not a
passing suite. Its stale acceptance/scheduler fixture issues were corrected and
checked separately. The Windows routing-authority fixture expects a qualification
error but gets `Unsafe protected record custody`; the same exact failure was
reproduced in the shared M1 checkout. Its routing-authority source and test are
unchanged between `14a69a0` and `1fd17ab` (confirmed by Git diff). No protected
custody guard was weakened to pass that test. Three connected scheduler cases
are excluded from the final bounded run; the pinned OpenJiuwen environment and
connected execution remain unqualified here. Exact final selection, exclusions,
logs and JUnit live in the notebook evidence receipt.

`freeze_planner_release.py --check` verifies the Planner and affected PDF release
pins. Git whitespace checks pass. The earlier 115-check combined suite passed
after refreshing working bytes; it preceded the final expanded selection.

A genuinely non-seven-node Planner proposal has not been demonstrated through
Planner, accepted freeze, real Scheduler dispatch, independent output checks and
terminal delivery in this review. Generic graph validation and controlled
Planner freeze are narrower evidence. Authenticated model quality, Docker/SSH,
ARM64/Spark, scientific execution and production calibration remain unverified.

## Integration with work owned elsewhere

| Boundary | Preserve | Check when the owner's branch arrives |
| --- | --- | --- |
| RSI / Library | Candidate generation cannot grant standing; independent qualification, sandbox versus live effect scope, explicit promotion, immutable versions and run pins | Candidate bytes and interfaces at actual incoming SHA; negative unqualified/unauthorized promotion; new snapshot sees eligible release while old frozen plan stays unchanged |
| Model router | Binder/runner owns protected selected-Capsule export; route owner selects model/provider; finalized contract precedes route decision; call evidence joins exact pins | Router absent/off fallback, timeout/invalid reply fallback before call, invalid bound-context halt, failure after call begins without changing model; route/call evidence |
| Planner and both owners | Accepted Brief, exact selectable catalog, protected checks, D20 declaration/output-only semantic review, budgets and effects | A small generic connected success, rejected output cannot advance, dependent-node blocking and protected-stop behavior |

RSI and router are not implemented here. Existing seam checks do not qualify
future branches or make an unknown incoming implementation merge-ready. The
maintained architecture authority remains the separate `jiuwenswarm` design-owner
checkout; branch-local received design snapshots do not supersede it.

## Later integration sequence

1. Pin the completed shared M1 and the incoming owners' actual branch commits;
   inspect their changed interfaces and tests. Keep the deliberate revert in history.
2. Agree the deployment restoration point after ongoing M1 changes. Reintroduce
   the desired deployment delta as a new reviewed change from that current base;
   do not assume merging old already-reverted ancestry restores it.
3. Reconcile this combined Planner/capsule candidate with that base, preserving
   the required core Planner. Resolve the known OPERATIONS modify/delete conflict
   using the chosen deployment behavior; do not revive the optional Planner.
4. Recheck exact release bytes and affected source closures on a fresh checkout.
   Qualify selected checking assets and activate only desired optional releases.
5. Run the connected generic success/failure scenarios and one actual campaign.
   Record environment, source/image pins, outputs and independent gates; only then
   decide runtime acceptance and deployment.

Two bounded `gpt-6-luna` reviewers handled workflow review and merge/state review;
the supervisor checked authority, contradictions, source deltas and test results.
Follow-up fixes stayed in named files. This is a focused integration review, not
an exhaustive comparison of every PRD clause or proof all implementation mistakes
have been found.
