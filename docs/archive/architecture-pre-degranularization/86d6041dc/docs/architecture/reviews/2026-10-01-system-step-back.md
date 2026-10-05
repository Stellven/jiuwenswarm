---
type: review
status: processed
tags: [review, step-back]
---

# Step back, 2026-10-01: the system layer

A fresh Opus agent, with no session context, read only the vault and PRD 3.0 to 3.2. It walked one M1 run end to end (CLI, launcher, freeze, generic script, `intent` and its gate, `requirement` and its gate), checked PRD coverage, and checked the whole graph. **Verdict: holds after fixes.** Each finding was checked in source before it was applied. Two were confirmed in agent-core at `9e339019`:
- the workflow loader requires a top-level `META` literal (`agent_teams/workflow/engine/loader.py:97-110`);
- `run_workflow` re-raises a script's exception after emitting `WORKFLOW_FAILED` (`agent_teams/workflow/engine/runner.py:268-273`).

| # | Finding | Severity | Disposition |
|---|---|---|---|
| B1 | What fills `Binding.verifier`, and which criteria the gate capsule gets, had three or four definitions | blocker | fixed. Deterministic `step_checks` run in Tier 1; judged `step_checks` go to the gate capsule in Tier 2; `every_step_gated` requires the gate capsule and at least one judged step check (PRD 4.2's two tiers on every node); freeze pins `gate_capsule_name` in `verifier`; `run_plan` gains `step_checks` |
| B2 | The launcher's order of calls had three versions | blocker | fixed: one ordered sequence in [toolchain M01](../capsule/toolchain.md#m01-launcher) |
| M1 | Code placement broke `adapters_only` | major | fixed: `CcBackend`, `cc_node` and the generic script live in `cc.adapters.swarmflow`; each adapter lists its own functions |
| M2 | `CallContext`, `ModelReply`, `complete` and `check(...)` defined twice | major | fixed: `ModelCallContext` and the model contract live only on the runner page; seams links to it |
| M3 | Two store APIs | major | fixed: the runner uses the M12 `Store` API |
| M4 | Hand-wired script examples | major | fixed: the runner links the generic script; open issue 7 closed |
| M5 | The halt host was undefined | major | fixed: [toolchain M03h](../capsule/toolchain.md#m03h-halt-host) |
| M6 | The generic script lacked `META` | major | fixed |
| M7 | "A gate capsule returns its decision" against "the judge never decides" | major | fixed in [capsule](../capsule/capsule.md#rules) |
| M8 | The gate call's input path was undefined | major | fixed in [seams](../seams.md#evaluator-gate-and-verifier) |
| PRD | 3.0.1 interception, 3.1.3 profile binding, 3.1.5 rejection had no page or reason | flag | 3.1.3 and 3.1.5 fixed in toolchain M01; 3.0.1 written up as [open issue](../open-issues.md) 28 |
| minor | `record_input` missing `vocabulary_ref`; Codex `request_id`; `cc.run.finished` payload; event timing; Binding writer name; stale requirement paragraph; node template sections; the requirement precondition; cancelled calls and Verifications | minor | fixed |
