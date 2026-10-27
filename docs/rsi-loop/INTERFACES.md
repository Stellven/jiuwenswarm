# RSI capsule improvement loop — shared interfaces (2026-10-27)

This file is the contract between the parallel workstreams (W1–W5). Change it
only by agreement with the orchestrator; every agent must read it first.

## Goal (acceptance bar)

A user click on **Run** in the UI at http://127.0.0.1:5175 for a capsule
(`utility.calculate`, `utility.table_normalize`, or any capsule registered in
`jiuwenswarm/research_rsi/targets/capsules.py`) must:

1. run **N iterations** (configurable, default 5) of
   diagnose → propose → sandbox-evaluate (parent vs candidate, public + held-out
   cases) → score → keep-best → feed scores/failures into the next proposal;
2. publish the full lineage (every iteration, every candidate, every score,
   including failed/poor candidates) without deleting Screening or earlier
   history;
3. leave the Run button re-runnable for a fresh revision without manual Root
   re-preparation;
4. stay UNQUALIFIED / SECURITY_DEFERRED; no production signing, admission or
   activation; Builder stays unavailable.

Fixes must be **general** (AGENTS.md rule 5): no per-run constants, no
hard-coded case answers, no special-casing of `calculate`/`table_normalize`.

## Ownership (files each workstream may edit)

| WS | Owns | Must not edit |
|----|------|---------------|
| W1 pipeline closure & sandbox | `deploy/m1/rsi_capsule_launcher.py`, `rsi_capsule_prepare.py`, `jiuwenswarm/research_rsi/capsule_doctor.py`, `targets/capsule_executor.py`, `targets/capsule_runtime.py`, new `targets/capsule_local_dispatcher.py`, their tests | `capsule_session.py`, `rsi_capsule_run.py`, `targets/capsules.py` |
| W2 improvement loop | `jiuwenswarm/research_rsi/capsule_session.py`, `deploy/m1/rsi_capsule_run.py`, new `jiuwenswarm/research_rsi/capsule_loop.py`, new `jiuwenswarm/research_rsi/model_backends.py`, their tests | `targets/*`, launcher/prepare/doctor, server, frontend |
| W3 objective | `targets/capsules.py`, new `targets/capsule_objective.py`, `jiuwenswarm/research/capsule_extensions/**` (fixtures/cases only, not worker bodies), their tests | session/run/launcher/server/frontend |
| W4 authority (after W1+W2) | `jiuwenswarm/server/rsi/cc_rsi_capsule.py`, `cc_rsi_broker.py`, `deploy/m1/rsi_capsule_broker.py`, `rsi_capsule_publication.py`, `rsi_capsule_launcher.py` (coordinate), their tests | loop, targets, frontend |
| W5 UI/server projection | `jiuwenswarm/channels/web/frontend/src/features/rsi/**`, `jiuwenswarm/server/rsi/cc_rsi_projection.py`, `jiuwenswarm/gateway/channel_manager/web/research_http.py`, their tests | everything else |

## Interface A — evaluation callback (W1 provides, W2 consumes)

The Root-side evaluator must serve an **arbitrary number** of evaluation
requests per session, bounded only by the plan's `maximum_executions`.

```python
# Provided to the session through `runtime.evaluate`
async def evaluate(role: str, body: bytes, *, iteration: int, trials: int = 1) -> dict
# role: "parent" | "candidate"
# returns a *visible result* dict:
{
  "schema": "ai4r-rsi-whole-capsule-visible-result:2",
  "role": role, "iteration": iteration,
  "subject_sha256": "<sha256 of body>",
  "passed_count": int, "case_count": int,
  "protected_wall_s": float,                 # sum over cases (single trial)
  "trial_wall_s": [float, ...],             # per-trial totals when trials > 1
  "rows": [ { "fixture_id": str, "fixture_set": "public" | "held_out",
              "task_success": bool, "protected_wall_s": float,
              "output_bytes": int, "checks": {...}, "receipt": {...} } ],
  "executions": int,                        # protected jobs this call used
  "failure": None | {"exception_type": str, "message": str}
}
```

Existing visible-result v1 readers must keep working (publication of the
historical Screening and R1/R2 records is never retrofitted).

`WholeCapsuleDispatcher` keeps its current constructor/`dispatch` signature.
W1 adds `capsule_local_dispatcher.LocalDispatcher` with the **same** interface
that runs the captured runtime program in a plain subprocess (no bwrap, no UID
switch) so the full loop is testable on any Linux box. The bwrap/V18 path stays
the production path and is selected by configuration, never by autodetection.

## Interface B — scoring (W3 provides, W2 consumes)

```python
# jiuwenswarm/research_rsi/targets/capsule_objective.py
def fixtures(name: str, *, fixture_set: str) -> list[dict]
#   fixture_set in {"public", "held_out"}; rows have id, packet, expected_task_output
def score(parent: dict, candidate: dict, *, noise: dict | None = None) -> dict
#   parent/candidate are visible results (Interface A).
#   returns:
{
  "correctness": {"parent": float, "candidate": float},     # fraction passed, public+held_out
  "latency_ratio": float | None,     # candidate / parent protected wall, None if not comparable
  "noise_floor_ratio": float | None, # from `noise` (repeated parent trials) or None
  "above_noise": bool,
  "improved": bool,                  # correctness >= parent AND (correctness > parent OR latency improved above noise)
  "regressed": bool,
  "summary": str,                    # one human line
  "feedback": str                    # text the proposer gets next iteration: failing case ids, diffs, timings
}
def calibrate_noise(parent_trials: list[dict]) -> dict   # from >=3 parent visible results
```

`public_fixtures(name)` in `targets/capsules.py` keeps its signature (used by
publication and existing tests). Held-out cases are never shown to the model;
only their pass/fail ids and the failure diff go into `feedback`.

## Interface C — session result schema (W2 produces, W4/W5 consume)

`capsule_session.execute()` returns a superset of today's result:

```python
{
  ...existing fields (status, parent_visible, candidate_visible, candidate_ref,
     rationale, diagnosis_ref, model_calls, limitations, ...)...
  "loop": {
    "schema": "ai4r-rsi-capsule-loop:1",
    "max_iterations": int, "completed_iterations": int,
    "stop_reason": "max_iterations" | "no_progress" | "budget" | "deadline" | "error",
    "model_backend": {"kind": "host-codex" | "fake" | "openai-compatible" | "anthropic", "model": str, "pinned_sha256": str},
    "iterations": [
      {"iteration": int, "diagnosis_ref": str, "proposal_ref": str,
       "candidate_ref": str, "candidate_sha256": str, "rationale": str,
       "visible": <Interface A result>, "score": <Interface B result>,
       "kept": bool, "model_calls": int, "elapsed_s": float}
    ],
    "best": {"iteration": int, "candidate_ref": str, "score": <Interface B>} | None,
    "parent_visible": <Interface A>, "noise": <calibrate_noise output> | None
  }
}
```

`candidate_visible`/`candidate_ref` at top level refer to the **best** kept
candidate (or the last one if nothing improved), so existing publication keeps
working.

## Interface D — authority (W4)

- A **durable development slot**: one Root-prepared slot per capsule that does
  not expire mid-run and is automatically re-prepared (new revision) after each
  terminal run. Finite expiring grants remain available as `strict` mode via
  configuration; default for development is `durable`.
- Journal, signing with the existing gateway key in place, consumed-claim
  semantics and the audit trail are kept. No ledger/journal/Core resets.
- Publication must handle every terminal state (success, partial, interrupted,
  startup failure) from retained evidence without re-execution.

## Test & tooling conventions

- Run focused suites with:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -o addopts= -p no:cacheprovider -p asyncio --confcutdir=<dir> <dir> -q`
- Baseline on this box before any change: `tests/unit_tests/research_rsi` 648 passed / 23 failed. The 23 are environment-specific (UID 12003 worker identity, Linux custodian, bwrap). Make them pass where the environment can be prepared (e.g. create the 12003 user) or mark them with a precise `skipif` that names the missing capability — never delete or loosen them.
- Fake models for tests live in `model_backends.py` (`FakeBackend(scripted_responses)`); they must drive the *real* loop code.
- Commit on your worktree branch with descriptive messages. Do not touch files outside your ownership column; if you must, stop and say so in your report.
