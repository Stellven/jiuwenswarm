---
type: review
status: processed
tags: [review, gates]
---

# Review, 2026-10-01: gate capsules and gate tooling

The area loop for the gate capsules ([gate host](../capsule/gate-host.md), [gate capsules](../capsule/gate-capsules.md), [intent gate](../m1/intent-gate.md), [brief gate](../m1/brief-gate.md), and toolchain M03, M03h, M10a, M13, M14).

## Canary

Two fresh agents each derived `research.accept_brief` blind (the gate node pages hidden). `arch_lint.py canary --compare` gave **agree** for A against the vault's own Declaration, B against it, and A against B. Their guesses were all about free text (summary wording, descriptions, `SKILL.md` wording), plus three documentation gaps: whether a work capsule's rubric is copied, where `gate_checks.py` goes, and whether an empty `rubrics/` is allowed. Each was fixed in [the pattern](../capsule/gate-capsules.md) and is recorded there as fixed or the author's own.

## Opus review: verdict "after fixes"

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | Two owners for the gate-capsule call (gate host against M10a) | blocker | fixed: M10a runs deterministic and reference checks only; the gate host calls the gate capsule; runner, seams and types updated |
| 2 | The first two-step run could not pass freeze (`objective_faithful` needed an undesigned admission judge) | blocker | fixed: the criterion is the step check `brief_objective_faithful`, judged by `research.accept_brief`; the requirement capsule admits with deterministic checks only |
| 3 | The step-check rubric hash is brittle | major | fixed differently from the proposal: the plan pins the rubric by hash, as CC pins everything; freeze refuses a mismatch with its own code, `GATE_RUBRIC_MISMATCH`; a new rubric is a new gate version plus a plan update. The proposed nullable hash would have been an exception to the Check shape |
| 4 | Freeze's gate rules were written twice | major | fixed: one list in toolchain M03 step 5 |
| 5 | A runtime failure of the judge was blamed on the wrong party | major | fixed: `ENVIRONMENT_BLOCKED` also reads the gate call's reason; R1 skips, so a resume re-runs |
| 6 | The `within_budget` test was unreachable | major | fixed: the test now expects `blocked`; `within_budget` is a backstop |
| 7 | The order and contents of Verification results disagreed | major | fixed in the Verification page and the gate host |
| 8 | The admission order was written twice | major | fixed: hash before rules, as the library page says |
| 9 | Check mode was unspecified | major | fixed: runner `--mode check`; M10a resolves Binding entries; the check library is stored by hash |
| 10 | Gate test cases compared nothing | major | fixed: third pattern check `assessment_matches_expected` |
| 11 | Multi-line quotes could not match | minor | fixed: whitespace is collapsed before comparing |
| 12 | The referee held only by convention | minor | fixed: `rsi_cannot_grant` also forbids checks and runner files |
| 13 | No envelope when the gate host failed | minor | fixed in the runner |
| 14 | A dead cancelled branch; "never stored" | minor | fixed: marked defensive; reworded |
| 15 | Author kit gaps | minor | fixed: `--gate` implies skill; `--store` |
| 16 | Template, budget and label wording | minor | fixed |
| 17 | PRD 3.1.5's deferred sense check had no owner | minor | fixed: the intent gate's `unknown` path |
