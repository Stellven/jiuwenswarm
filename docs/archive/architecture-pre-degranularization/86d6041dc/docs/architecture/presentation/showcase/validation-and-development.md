# Validation and development

[Start here](README.md) · Documentation evidence is separate from runtime acceptance

## Current correction and readiness

The main flow now gates intent and requirements before DAG planning, binding and local execution. Existing intent hint semantics, requirement inputs, experimental-only planner requests, capsule inventory and fixed-template fixtures need connected revision. Their old passing checks do not establish coding readiness for the new flow. [Control flow](../../m1/control-flow.md) lists affected owners.

## Evidence categories

- **Specified design:** a contract and expected behavior are written at an owning page. Draft does not mean implemented or approved.
- **Documentation checked:** a named command/review checked a particular source revision. Check freshness before reusing the result.
- **Implementation validation pending:** runtime behavior, real platform/security enforcement, authentication, crash durability and measurement accuracy need executed tests after coding.
- Existing documentation evidence at revision `1c09e8394` is recorded in [diagram review](../../reviews/2026-10-05-overall-diagrams-review.md): canonical diagram inventory, all four 23-binding flow views, schema/examples and navigation checks. This is historical baseline evidence, not evidence for the corrected planner-driven flow.
- [Previous snapshot review](../../reviews/2026-10-05-showcase-review.md) records the superseded fixed-plan package. Current correction checks cover diagram/navigation freshness only; revised interfaces still need source review and seam validation.

## Failure scenarios to implement

- Missing files, wrong versions, invalid hashes/references, unknown fields and forbidden effects: reject before the affected call.
- Duplicate requests, changed bytes under a duplicate ID, timeout and cancellation: preserve the correct reservation/result and prevent silent repeated model calls.
- Output commit failure, Gate decision commit failure, release commit failure and interrupted publication: prevent unauthorized next-node dispatch; recovery uses committed evidence.
- Denied paths, network, credentials and hidden fixtures: demonstrate enforcement at the actual worker boundary, not just declaration parsing.
- RSI exhausted budgets, invalid mutation, inactive candidate and unauthorized activation: refuse and preserve evidence.
- Invalid experimental proposal, changed alias between validation/freeze and experiment/production configuration mix: zero unauthorized dispatches.
- Scientific negative/inconclusive results: retain valid evidence and produce the permitted report without confusing scientific classification with Gate status.
- [Verification](../../system/verification.md) owns invocation points and expected records. [Stories](../../stories/README.md) provide end-to-end examples. These are designed scenarios, not executed product tests.

- Screening with no eligible opportunity: record `NO_ELIGIBLE_OPPORTUNITY`, emit no successful card, halt before Hypothesis and enter human review. See [Screening](../../m1/screening.md). This is distinct from a valid negative scientific result.

## Review and maintenance policy

- Update one canonical owner, then its producers, consumers, Gate, records, examples, diagrams and handoff links in the same connected change.
- Run schema/example, link, generated freshness and diagram checks first. Fresh reviewers then inspect source fidelity and failure/authority paths; resolve findings against sources. [Bounded review workflow](../../review-workflow.md) owns review allocation.
- Record what ran, against which bytes, and what remains unrun. Repeated AI agreement is not evidence of runtime correctness. Only explicit approval changes a page to locked.
- SkillFuzz interaction analysis remains deferred. It must not appear as completed evidence or a current handoff gate. Reopen the relevant design when the campaign's scope and acceptance criteria are adopted.

## Coding handoff

- [Coder requirements](../../system/coder-requirements.md) asks seven questions: placement, interfaces, control flow, persistence, security, environment and verification.
- [Handoff](../../system/handoff.md), [module map](../../system/modules.md) and [build order](../../system/build-order.md) link exact owners and prerequisites. A coder can invoke each boundary independently with fake adjacent services before joining the full workflow.
- Architecture defines contracts and expected observations. The downstream team creates Spec Kit, code, tests and actual results. No measured optimization or complete-system safety claim is supplied by this package.

[Return to index](README.md)
