---
type: review
status: draft
version: 1
owner: muk
sources: [../../product/SOURCE_FREEZE.md, ../system/planner.md, ../system/environment.md, ../system/model-auth.md, ../system/storage.md, ../system/records.md, ../system/experiments.md, ../capsule/runner.md, ../capsule/gate-host.md]
tags: [review, adversarial, planner, security, m1]
---

# Adversarial design review, 2026-10-05

This review tries to turn valid-looking inputs, interruption windows and confused authority into unauthorized execution or false evidence. It is a documentation review and a downstream fault-fixture specification. No attack was executed against the product. No finite review demonstrates an unbreakable system.

## Scope and trusted boundary

Inspect the fixed production plan, isolated Leader planner, protected Codex bridge, durable Gate/release ordering, credential custody, storage references and RSI/experimental separation. An attacker controls submitted task text, retrieved research text, model response, a candidate capsule implementation or an interrupted client. Trusted supervisor, profile authors, local authenticated owner, kernel and verified container image are outside that adversary. Compromise of those authorities is a distinct threat; Docker alone does not remove it.

Preserve authenticated caller identity, exact immutable pins, minimal workload mounts, private fixture custody and required capture. Never treat syntactic validity, a model explanation, a developer allowlist or a persisted but unrelated PASS as execution authority. Owner pages define normative behavior; this review links them and supplies adversarial cases rather than duplicating schemas.

## Findings and design disposition

| ID | Design weakness found | Disposition and owner |
|---|---|---|
| A1 | `validation_request.plan_ref` could name bare run_plan, dropping selections/objective/budget metadata | [planner proposal envelope](../system/planner.md#proposal-envelope-and-reference-semantics) requires a planner_proposal Artifact; normalized run_plan has a separate validated_plan_ref |
| A2 | Planner runs before Binding, while old bridge run scope requires a frozen Binding | [planner authority](../system/planner.md#codex-provider-and-pre-freeze-authority) uses a supervisor-committed planning reservation and narrow pre-run scope; shared environment/schema must agree |
| A3 | Objective IDs were not mapped to the actual Brief schema | Bind mandatory requirement_id values and independently authored criteria; reject invented IDs and weakened criterion refs |
| A4 | Model budget estimate could understate nested/Gate calls | [resource accounting](../system/planner.md#resource-accounting) requires deterministic closure checks and broker reservation before each actual call; implementation enforcement remains unrun |
| A5 | PRD constraint extraction was cited as planner authorization | Planner now cites isolated experiment clause 6.12 and library clause 4.1.2; 3.2.4 only supplies extracted constraints |
| A6 | Model-call evidence field implied production required a fabricated model response | Draft `proposal_source_ref` differentiates captured model response from deterministic fixed-plan provenance; all schema/fixture consumers must use the same field |
| A7 | Production needed a Brief before freezing the capsule that produces that Brief | Fixed production envelope uses committed intake and empty objective bindings with an exact-template check; isolated planner requires Brief and mandatory bindings. Requirement and later Gates establish production semantic coverage during execution |

These fixes change shared interpretations and require producer/consumer/schema rechecks before coding handoff. A reviewed prose correction does not independently prove implementation acceptance.

## Attack and interruption fixtures

Each case is independently invocable with fake adjacent adapters and immutable fixtures. Assert committed records and successor invocation count, including zero on refusal; a returned error string alone is insufficient. Fresh fixture authors should derive expectations from the linked owning contracts, not the candidate implementation.

| Case | Attempt to break the system | Required outcome / observable evidence | Owning boundary |
|---|---|---|---|
| P01 | Prompt says to change track to production, activate a candidate or invoke a shell | Bounded model reply remains data; unauthorized node/effect rejects before workload dispatch; no alias mutation | [planner](../system/planner.md), [experiments](../system/experiments.md) |
| P02 | Valid run_plan but missing/duplicate/conflicting selection rows | INVALID findings; no validated plan or Binding | planner proposal envelope |
| P03 | Pass a bare run_plan or another task's proposal as plan_ref | Reject artifact type or mismatched exact input refs; zero dispatches | planner envelope, [store](../system/storage.md) |
| P04 | Map R1 to nonexistent output or a model-authored easier criterion | INVALID objective/criterion binding; no scientific success inferred | planner objective authority |
| P05 | Correct ports but hidden extra dependency, unadmitted external or unbounded nested closure | INVALID dependency/budget findings; no code load | [admission/freeze](../capsule/toolchain.md), planner validator |
| P06 | Use current alias B after validating snapshot A | Exact A pins or explicit revocation refusal; never B under A's evidence | planner, admission/freeze |
| P07 | Claim low call/time estimate while tool or verifier requests more | Policy-derived bound checked; broker refuses exhausted ordinal; halt, captured actual calls and no output success | planner resource accounting, [bridge](../system/environment.md) |
| P08 | Forge planning scope for another run, changed config or unreserved request | Refuse before paid turn; no captured result in attacker-selected scope | bridge authorization |
| P09 | Reservation saved but client disconnected before proposal response | Duplicate retrieves existing state/evidence; no second paid call; uncertain turn needs explicit review | planner, [lifecycle](../system/lifecycle.md) |
| P10 | Validator returns VALID then storage fails or normalized plan is replaced | No freeze/dispatch from in-memory or unrelated result; exact committed hashes required | planner, store |
| P11 | Disable Screening yet retain required Hypothesis input; disable capture/auth as ablation | INVALID before effect; no synthetic card or production authority | experiments |
| P12 | Native Leader approval or Code Mode response asks to rewrite a running plan | No live graph change; permitted results validate as ordinary data under the existing track | planner, experiments |
| P13 | Experimental proposal pretends to be production to omit objective bindings, or production mutates the fixed template | Track/task source and producer authorization cross-check; rejection before freeze; no new model-generated production workflow | planner track-specific entry |
| G01 | Reuse PASS Verification from another run/step/attempt or swapped Observation | Gate/ref relationship fails; no committed release or next invocation | [Gate](../capsule/gate-host.md), [records](../system/records.md) |
| G02 | Computed PASS, failed durable Verification write; or saved PASS but lost reply | First: halt/no release. Second: recover committed decision without rerunning work | records, lifecycle |
| G03 | Kill process after effect before Observation; same request arrives twice | Reservation retained, no terminal Observation is not proof of no effect; explicit reviewed restart/new attempt | records, lifecycle |
| G04 | Capsule fabricates broker error ID to hide its own defect | Trusted bridge matches exact recorded failed request; unmatched claim is capsule fault | [runner](../capsule/runner.md), environment |
| S01 | Ref with correct-shaped hash but wrong kind, namespace, membership or bytes | Refuse before use; schema validity never substitutes for custody/hash validation | store, records |
| S02 | Symlink/path traversal, surviving grandchild, direct socket, hidden fixture read | Validated execution service denies or profile is unavailable; actual negative probes required before readiness | [deployment](../system/deployment.md), [doctor](../system/environment.md) |
| S03 | Candidate tries oracle-private ref through public artifact/export endpoint | Namespace/principal denial; no private capture or expected answers in logs/export/model context | [oracle](../capsule/fixture-oracle.md), environment |
| S04 | Start second auth writer or restore stale auth seed after refresh | Exclusive persistent profile lock refuses contention; no stale overwrite or desktop profile coupling | [model authentication](../system/model-auth.md) |
| S05 | Include device code/auth.json contents in research context or benchmark export | Trusted setup-only challenge and bridge-owned credential home remain excluded; secret-exclusion fixture observes public payloads | model authentication, [benchmark export](../system/benchmark-export.md) |
| S06 | Model timeout/cancel followed by reconnect repeats possibly paid turn | Captured terminal/uncertain state, bounded cleanup of bridge-owned child; no silent repeat or provider fallback | environment, lifecycle |
| R01 | RSI scores candidate then activates itself, changes referee, or leaks final suite | Frozen mutation/custody boundaries reject; candidate/admission/manual activation remain separate | [RSI](../capsule/rsi-engine.md), oracle, library |
| R02 | Oracle interrupted query is refunded or final holdout reused to tune candidate | Reserved quota remains consumed; final phase/once-per-session state enforced; no proposal access to final evidence | oracle |

## Residual risks and evidence needed

- Kernel, container bootstrap identity, namespace confinement, mounted paths, clock/counter enforcement and pinned app-server cancellation must be demonstrated on the supported platform matrix. Review cannot substitute for those probes.
- Semantic verifier false positives and scientific measurement manipulation require independently authored known-good/known-bad fixtures, trustworthy measurement capture and held-out cases. Deterministic graph validity is not semantic correctness.
- The authenticated local owner can authorize policies and activation; that permission is intentionally powerful. Attribution, immutable history and narrow namespaces make changes inspectable rather than claiming the owner cannot misuse authority.
- A provider or upstream document may change after this review. Source pins, doctor checks and replacement boundaries remain necessary; precedent citations justify a pattern, not a certification of this system.

## Verification record for this review

Inspected owning Markdown contracts, services-v1 planner definitions, run-plan schema source, frozen PRD clauses and existing story 07. Identified A1–A7 by cross-reading those files; edited the planner owner page. Shared schema/environment and consumer updates require the coordinating author's recheck. Product/security fault executions above remain **not run**. The coordinating quality record owns exact subsequent lint/schema/check command results and fresh review dispositions.

The design follows typed bindings from [Kubeflow component specifications](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/), explicit dependency closure from [Bazel](https://bazel.build/concepts/dependencies), and policy/enforcement separation from [Open Policy Agent](https://www.openpolicyagent.org/docs/philosophy). These primary sources were checked October 5. The local constraints and custody mechanisms must still be verified independently.

## Fresh integrated review and finding closure

A separate fresh reviewer read the revised owners, selected frozen PRD clauses and pinned Leader/Codex source without editing them. It found three additional issues: F1 launcher/freeze still accepted a bare plan and ordered validation before intake; F2 the durable quota record omitted per-call subject identity; F3 hidden-case wording incorrectly prohibited authorized oracle-private case inputs. The coordinator fixed F1 in M01/M03 and planner, F2 in the canonical reservation schema/records and broker semantics, and F3 in the benchmark custody text. The reviewer independently reread the fixes and reported all three closed at the design-contract level, including production versus planning authority clarification. No remaining mismatch was found in that targeted reread.

The review was bounded, not an exhaustive proof over every PRD clause. Structural stage/track navigation, schema, link, graph and source-hash checks are recorded in the [work checklist](2026-10-05-work-checklist.md). Runtime fault cases and residual kernel/provider/semantic risks above remain unexecuted implementation obligations. No reviewer approval claims an unbreakable implementation.
