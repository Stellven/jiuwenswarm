---
type: capsule
tags: [capsule, trust]
---

# Trust

How much the system trusts a capsule is never a score. It is a small set of facts, each written by one party and each checkable:

| Fact | Where it is | Who writes it | What it says |
|---|---|---|---|
| **Level** | [Verdict](../schemas/verdict.md) `level` | admission | how the capsule was tested: `exempt`, `provisional` or `certified` |
| **Standing** | [Standing](../schemas/standing.md) `state` | admission, then the librarian | whether this version may be used now |
| **Pinning** | Declaration `needs.external`, `needs.dependencies` | the author | every dependency is pinned, so nothing changes under a version |
| **RSI permission** | Declaration `evolution.rsi` | the author | whether RSI may change it |
| **Gate results** | [Verification](../schemas/verification-record.md) | the gate | whether one call's output passed |

## Levels

The exact rules for each epoch are in the policy's `levels`.

| Level | Earned by | M1 |
|---|---|---|
| `exempt` | no assurance suite is required; `puppet_admission` grants it only when a developer policy allowlists the exact `decl_hash`, after mandatory declaration/hash/dependency/permission/interface validation. Every call records a trajectory, and every output still passes its real runtime Gate | checked |
| `provisional` | at least one test case, and every check on its test calls passes, including its `node` and `both` checks | checked |
| `certified` | also a sealed suite passes, written by someone other than the builder | unchecked |

The level says what admission evidence exists; Standing and the active alias say whether the version may be bound. The runtime Gate still checks every governed output. A Puppet decision cannot grant `certified`, activate an RSI child, change permissions or create a runtime Gate result.

## What lowers trust

- **Nothing floats.** Every dependency is pinned in every version: capsules by `decl_hash`, packages by the lockfile. So a `decl_hash` means one set of code everywhere, and a newer dependency arrives only as a new, tested version ([updating dependencies](rsi.md)).
- **A security fix does not wait for RSI.** When a pinned dependency has a known vulnerability, the librarian moves the capsule to `suspect` or `revoked` at once, and so every capsule that pins it. A fixed version comes from RSI if the capsule allows it, or from its author. Until then the capsule is unavailable, by design.
- **A remote capsule.** An `mcp` or `a2a` service we cannot hash is pinned by endpoint and version; the pin proves what was pinned, not what the service runs. So a remote capsule, and any capsule that depends on one, cannot be `certified`.
- **Drift or a lost member.** The librarian moves the Standing to `suspect`; a revoked dependency or member does the same to capsules that use it.

**Observation may withdraw authority; only a checked declaration may grant it.** Only admission raises trust. The librarian, Findings and gates only lower it.

## Block for safety, label for quality

A breach of a declared effect, a failed deterministic check or a changed hash stops a call. A weak but safe result passes with a label (Artifact `issues`), so work continues and the weakness is recorded. Judged checks are not calibrated yet, so a judged `fail` is meant for a person to review; how the first epoch folds it is in the policy `blocking` section.

## Referees

Any node may be a capsule, including gates and verifiers. The actor may improve; the referee may not: **gates are not RSI-able for now**: a capsule used as a gate or verifier must have `evolution.rsi: none`, and freeze refuses a Binding that uses any other as a gate or verifier (rule `referee_no_rsi`). Gates are chosen by the workflow, never by the capsules they check, and no capsule may gate its own output (INV-10).

## How trust meets permissions

A capsule's declared effects, network and secrets become permission rules in jiuwenswarm; its level and Standing decide whether it may be bound at all. See [permissions](permissions.md).

## Open: trust detail in earlier drafts, not in the schema now

Schema v2.10b had finer trust, left out of v1 to keep it small. Each could come back as an unchecked field:

- **Per-promise assurance**: `enforced` > `tested` > `audited` > `declared`, since file and network effects are only enforced inside a sandbox.
- **Claim status** on outputs: `supported`, `unsupported` or `stale`, with a reason, so delivery can say which results rest on unmeasured judges.
- **Judge standing**: `unmeasured`, `calibrated` (30+ items with injected defects), `measured` (200+ items), from spot checks.
- **Requiring a level at a call site** (`requires_certified`).
