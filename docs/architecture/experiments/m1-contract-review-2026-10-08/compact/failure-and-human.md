# Failure handling and human callback

**Reading level: human potential.** Question answered: What happens when work blocks, faults, restarts or needs a human?

## When to call the human

| Event | Autonomous behavior | Human callback |
|---|---|---|
| Empty/unreadable intake; unsupported domain or mandatory input | Reject before work dispatch, retain rejection reason | Show actionable input correction at the submitting surface. It does not start a semantic clarification dialogue. |
| Material intent/requirement ambiguity or conflicting constraints in Intent Compilation and Verification Slice (formerly TRIAL-1)/Delivery Phase 1, or after Delivery Phase 3 clarification is exhausted | Evaluator Gate records a non-advancing result; halt | Ask the user to correct the source objective or supply the missing permitted input. New submission creates a new run. |
| Work execution fault, invalid artifact, mandatory semantic failure | Record `FAIL`, stop new dispatch | Triage request with failed obligation, exact subject, available evidence and permitted next action. |
| Unauthenticated/unavailable model, missing dataset/dependency, timeout preventing valid evaluation | Record `ENVIRONMENT_BLOCKED` where dependency failure prevents a valid judgment; halt | Request the specific environment repair. A demonstrated implementation defect remains `FAIL`; uncertainty stays explicit. |
| Insufficient evidence or unresolved verifier judgment | Record `INCONCLUSIVE`, halt | Request inspection/additional evidence. Human opinion alone cannot satisfy a mechanically or scientifically required observation. |
| Denied effects, fixture access, permission escalation, budget exhaustion | Contain/terminate affected execution; halt whole run | Security or resource triage. No “allow once” override of frozen restrictions, no live budget increase or route substitution. |
| Persistence failure before release | Block readiness, retain whatever evidence can safely persist; no pass | Operational alert via the control plane. If durable recording is unavailable, display the failure and return non-success; do not claim a persisted triage record. |
| `PASS_WITH_KNOWN_LIMITATIONS` with all mandatory checks satisfied | Advance, carry warnings into downstream evidence/report | No blocking callback; warnings visible immediately and disclosed at delivery. |
| Valid scientific rejection or scientific inconclusive result | Infrastructure verifier may pass; proceed to Delivery | Deliver the scientific result and follow-ups. No mandatory intervention merely because the hypothesis failed. |
| User cancels | Stop new dispatch; contain active work; preserve effects/evidence | Acknowledge cancellation; do not generate a redundant failure question. |
| Browser disconnect | Continue server-owned execution | No callback solely for disconnection. A later failure remains visible on reconnection. |
| Engine restart interrupts unfinished work | Preserve accepted artifacts, mark interrupted attempts paused; no replay | Show interruption and evidence to the human. Recovery is inspection and a fresh run in M1, not automatic in-place resumption. |

| Mode | Delivery of a blocking callback | Waiting and replies |
|---|---|---|
| Web / Intent Compilation and Verification Slice | Existing run status and native interaction surface, with reason and evidence references | Server releases execution resources after halt. An unattended request remains durable and visible when the user reconnects. No detached terminal is spawned. |
| Interactive CLI/TUI / full M1 | Native `human_session` triage through the current authenticated session | The interaction may wait for inspection/acknowledgment, but the research run is already halted. Disconnecting or dismissing does not resume it. |
| Headless development/evaluation / Intent Compilation and Verification Slice and full M1 | Stable machine-readable non-success, detailed verdict/reason, `run_id` and bundle reference when available | Never invoke an input prompt or wait on `human_session`. Record human action needed for later inspection; benchmarker continues its campaign policy. |

## What a human may do

Inspect or acknowledge the halt, abort the triage session, repair the environment, correct the objective, supply permitted resources, or explicitly initiate fresh attributable work. Record the actor, answer and changed inputs. Keep the failed run and its verdict unchanged. A new run records its relationship to the previous one, re-resolves configuration and eligible pins, re-freezes its plan, and performs all required checks. No correction edits an accepted artifact in place.

## Delivery Phase 3 clarification before acceptance

## Offline RSI is a separate callback policy

A normal candidate score decline or compatibility rejection records evidence and can feed the bounded offline search; it does not ask the user on every attempt. Query/resource exhaustion ends the session and returns a summary. A security violation, degraded fixture boundary, referee fault or evidence tampering stops the session and requests operator triage. Hidden cases and per-case final feedback are withheld even from ordinary callback content.

## Pattern and reuse evidence

Use the existing **correlated human interaction pattern**: halt/record first, project attention to the current surface, bind a reply to the run and correlation ID. Combine it with the protected decision/release pattern already required by the PRD. This avoids inventing an agent that owns both evaluation and workflow authority.

## Connected behavior summary

Blocking execution, mandatory check, security, resource or persistence failure stops new dispatch; contain active work and retain evidence/effects. Failure, environment blocking and insufficient judgment remain distinguishable. Available triage records include subject/obligation, run/node/attempt, reason/evidence and permitted correction. Storage failure returns non-success without claiming a durable record.

Interactive sessions project a correlated native human_session/attention request after halt; replies bind exact run/session and stale/cross-run replies reject. Headless returns stable non-zero status immediately, never waits. Human can inspect/acknowledge/abort, repair environment or initiate linked fresh work; cannot override a mandatory check or overwrite failed history. New work re-resolves/re-freezes/rechecks. Browser disconnect does not cancel; restart pauses interrupted attempts without replay. Cancellation is explicit and cannot undo prior effects.

Phase 1 and immediate Intent are non-interactive compilation. Phase 3 declared pre-acceptance clarification can use frozen turn/time/call limits, source-attributed replies and independent subsequent checking. Exhaustion/material ambiguity/fault halts; headless uses supplied answers or halts. Accepted contracts never change through dialogue or execution repair.

PASS_WITH_KNOWN_LIMITATIONS advances only with all mandatory checks; valid scientific FAIL/INCONCLUSIVE proceeds to Delivery. Normal RSI candidate decline can feed bounded search; security/custody/referee fault stops session, resource exhaustion ends it. Hidden feedback stays restricted. Candidate remains inactive until required admission/human activation; rollback changes future standing only.
