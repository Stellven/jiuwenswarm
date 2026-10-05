---
id: capsule.trust
type: capsule
tags: [capsule, trust]
level: detail
status: proposed
provides: [capsule.trust]
depends_on: [fields.md, permissions.md, library.md, ../verification.md]
prd: [4.1.2]
---

# Trust

PRD: 4.1.2

> Answers: How much does the system trust a capsule at M1, and on what facts?

> M1 uses levels `exempt` and `provisional` only; `certified` and finer trust are in [future state](future-state.md).

How much the system trusts a [capsule](capsule.md#term-capability-capsule) is never a score. It is a small set of facts, each written by one party and each checkable:

| Fact | Where it is | Who writes it | What it says |
|---|---|---|---|
| <a id="term-level"></a>**Level** | [Verdict](../schemas/verdict.md) `level` | admission | how the capsule was tested: `exempt`, `provisional` or `certified` |
| <a id="term-standing"></a>**Standing** | [Standing](../schemas/standing.md) `state` | admission, then the librarian | whether this version may be used now |
| <a id="term-pinning"></a>**Pinning** | Declaration `needs.external`, `needs.dependencies` | the author | every dependency is pinned, so nothing changes under a version |
| <a id="term-rsi-permission"></a>**RSI permission** | Declaration `evolution.rsi` | the author | whether RSI may change it |
| <a id="term-gate-results"></a>**Gate results** | [Verification](../schemas/verification-record.md) | the gate | whether one call's output passed |

## Levels

The exact rules for each epoch are in the policy's `levels`.

| Level | Earned by | M1 |
|---|---|---|
| `exempt` | no assurance suite is required; `puppet_admission` grants it only when a developer policy allowlists the exact `decl_hash`, after mandatory declaration/hash/dependency/permission/interface validation. Every call records a trajectory, and every output still passes its real runtime [Gate](../verification.md#term-gate) | checked |
| `provisional` | at least one [test case](../schemas/checks.md#term-test-case), and every check on its test calls passes, including its `node` and `both` [checks](fields.md#term-check) | checked |
| `certified` | also a sealed suite passes, written by someone other than the builder | unchecked |

The level says what admission evidence exists; Standing and the [active alias](library.md#term-alias) say whether the version may be bound. The runtime Gate still checks every governed output. A Puppet decision cannot grant `certified`, activate an [RSI child](rsi.md#term-parent-and-child), change permissions or create a runtime Gate result.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-referee"></a>**referee** | The fixed code and the one verifier capsule that decide what passing means, protected from RSI. The actor may improve; the referee may not, and the binder refuses any other capsule as a verifier. |

## What lowers trust

- **Nothing floats.** Every dependency is pinned in every version: capsules by `decl_hash`, packages by the lockfile. So a `decl_hash` means one set of code everywhere, and a newer dependency arrives only as a new, tested version ([updating dependencies](rsi.md)).
- **A security fix does not wait for [RSI](../rsi.md#term-rsi).** When a pinned dependency has a known vulnerability, the librarian moves the capsule to `suspect` or `revoked` at once, and so every capsule that pins it. A fixed version comes from RSI if the capsule allows it, or from its author. Until then the capsule is unavailable, by design.
- **Drift or a lost member.** The librarian moves the Standing to `suspect`; a revoked dependency or member does the same to capsules that use it.

**[Observation](../schemas/observation.md#term-observation) may withdraw authority; only a checked declaration may grant it.** Only admission raises trust. The librarian, [Findings](../schemas/finding.md#term-finding) and gates only lower it.

## Block for safety, label for quality

A breach of a declared effect, a failed deterministic check or a changed hash stops a call. A weak but safe result passes with a label (Artifact `issues`), so work continues and the weakness is recorded. Judged checks are not calibrated yet, so a judged `fail` is meant for a person to review; how the first epoch folds it is in the policy `blocking` section.

## Referees

The actor may improve; the referee may not. The verifier (`research.verifier`, one identity reused by every Gate through pinned profiles) has `evolution.rsi: none` and zero RSI-mutable components, and the binder refuses a [Binding](../schemas/binding.md#term-binding) that uses any other capsule as a verifier (rule `referee_no_rsi`). Gates are attached by the binder, never chosen by the capsules they check, and no capsule may gate its own output (INV-10). See [verification](../verification.md).

## How trust meets permissions

A capsule's declared effects, network and secrets become permission rules in jiuwenswarm; its level and Standing decide whether it may be bound at all. See [permissions](permissions.md).
