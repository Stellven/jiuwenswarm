---
type: design
status: draft
tags: [design, draft, capsule, m1]
---

# CC against the PRD: schema check

> **Draft, not yet approved.** Checks the [capsule](../capsule/capsule.md) and [schema](../schemas/schemas.md) pages against the PRD, and says what should change. The schemas and CC tools are ours to decide. A change that touches RSI, the Verifier or model routing is marked **needs agreement** with its owner. The schema is not implemented yet, so the aim is the best schema, not the smallest diff. PRD points we push back on are in the [PRD review](prd-review.md).

## Verdict

**The schema covers every PRD requirement, and needs no restructuring.** Checking it found one real gap (which judge runs judged checks at admission) and four improvements worth making now. Everything else the PRD needs is content (port types, policy values) or tools, not schema.

## Where each PRD requirement is met

| PRD requirement | Met by |
|---|---|
| `make_capsule.md` contract with strict JSON I/O and acceptance rules (4.1) | the [Declaration](../capsule/fields.md): `ports` with `value_schema`, `guarantees.checks` |
| bounded workspace paths (4.1), workspace isolation (4.4) | `changes.effects[].resource_key`; enforcement is a tool gap on the Codex runtime ([permissions](../capsule/permissions.md#gaps-and-conflicts)) |
| code that runs is the code that was tested | `code_sha256` in the [Binding](../schemas/binding.md), checked at every load |
| whitelisted operators (section 3, 4.4) | operators as `tool` capsules, pinned in `needs.external` |
| Stage Evidence Bundle (4.3) | output [Artifacts](../schemas/artifact.md), the Declaration, the [Observation](../schemas/observation.md); the [Verification](../schemas/verification-record.md) reaches all three |
| tier 1 and tier 2 (4.3) | `deterministic` and `reference` checks, then `judged` checks by the Binding's `verifier`; [policy gates](../schemas/policy.md#gates) |
| `PASS`, `FAIL`, `BLOCKED` (4.3) | Verification `decision`: `pass`, `fail`, `blocked` |
| token budget ceilings (4.3) | `budget.tokens`, `cost.tokens`: present, unchecked until the adapter reports tokens |
| register, version, audit | [Candidate](../schemas/candidate.md), [Verdict](../schemas/verdict.md), [Standing](../schemas/standing.md); `decl_hash` is the version |
| suspend, deprecate, roll back | Standing states and `REVERTED`; see change 5 |
| RSI on fixtures, promotion only through admission (section 2) | `evolution.rsi`, Candidate, [checks](../schemas/checks.md) test cases |
| with and without `make_capsule.md` (section 3) | two sets of Declarations under one policy epoch, told apart by `decl_hash`; no schema change |

## Changes to make

**Applied to the schema pages on 2026-09-29.** Also applied then:

- a `nested` caller for operator calls, pinned through the parent's `needs.external`;
- freeze refusing changed code in a capsule or its pins;
- the reason codes `BUDGET_EXCEEDED`, `PORT_TYPE_MISMATCH`, `JUDGE_IS_SELF` and the `_BY_OWNER` codes;
- the RSI rules checked at M1, for Candidates from the RSI branch;
- development policy epochs that accept each other.

The table below keeps the reasons.

| # | Change | Why | Owner | Pages |
|---|---|---|---|---|
| 1 | **Name the admission judge.** The policy names the judge capsule admission uses for `judged` checks. Verdict `checks_run[]` gains `judge {judge_decl_hash, model}`, as Verification `results[]` has. A new rule refuses a capsule judged by itself | `provisional` needs every check on the test calls to pass, including judged ones. At admission there is no Binding, so nothing names the judge. It also decides how `verifier_capsule` is admitted, since it must not judge itself (INV-10) | CC; **needs agreement** with Verifier on which judge | [policy](../schemas/policy.md), [Verdict](../schemas/verdict.md), [invariants](../schemas/invariants.md) |
| 2 | **Check Artifact `issues` at M1, and adopt INV-19.** A capsule completes its contract and puts its caveats in `issues` | the report's "documented limitations" (PRD section 3, Delivery) need a standard place. It is also what `PASS_WITH_KNOWN_LIMITATIONS` would read. "Block for safety, label for quality" relies on it | CC; tell Verifier, who reads it | [Artifact](../schemas/artifact.md), [invariants](../schemas/invariants.md), [capsule](../capsule/capsule.md#when-a-call-goes-wrong-proposed) |
| 3 | **Give every reason code an owner.** The `reason_code` registry gets a column: `runtime`, `capsule`, `refusal`, `judge` or `input` | `blocked` today mixes a runtime outage, a capsule crash, a refusal and an undecided judge. With an owner per code, any tool can say whose fault a halt is without guessing, and "environment blocked" is reported only for `runtime` codes | CC; **needs agreement** with Verifier, whose verdicts would use it | [policy registries](../schemas/policy.md#registries), [Observation](../schemas/observation.md) |
| 4 | **Take the time budget from the capsule.** Check `needs.resources.timeout_s` at M1. The Binding's budget is the lower of it and the policy's cap | one fixed 600 s per call does not fit a long operator run (DeepSearch, to be confirmed). The field already exists; per-name values in the policy would be a second place for the same fact | CC | [fields](../capsule/fields.md#needs-what-must-hold-and-what-it-uses), [policy budgets](../schemas/policy.md#sections-with-proposed-values-for-the-first-epoch), [Binding](../schemas/binding.md) |
| 5 | **Let a person move a Standing.** Check `suspect`, `deprecated`, `retired`, `revoked` and reverts at M1, written by a librarian command acting for a person. Add reason codes for a person's move, such as `SUSPENDED_BY_OWNER` and `DEPRECATED_BY_OWNER` | the template's "suspend, deprecate" and "roll back". Standing `reason` is required, and no code today says "a person asked" | CC | [Standing](../schemas/standing.md), [policy registries](../schemas/policy.md#registries) |

## Content, not schema

- **Research payload types.** At M1, `json` ports with a pinned `value_schema` already give strict JSON. Add named types (`research_brief`, `idea_set`, `hypothesis`, `poc_bundle`, `research_report`) to the [port type vocabulary](../schemas/port-types.md) once a second consumer needs to match by type, such as Planner Phase 2.
- **Token budgets.** The fields exist. Mark them checked when the Codex CLI adapter reports usage (**needs agreement** with Model Routing, [PRD review](prd-review.md) point 5).

## Not needed

- **A stored five-verdict field.** It would copy what the Verification, Observation and Artifacts already say (INV-5). Derive it instead; see [gate verdicts](#gate-verdicts).
- **A second policy epoch for the experiment.** The arms are told apart by `decl_hash`.
- **Checking `needs.secrets` or Candidate `source` at M1.** Both are useful later (isolated verification, provenance of ported rubrics), but M1 works without them.

## Tools and docs, no schema change

- **A minimal librarian command** for change 5.
- **Workspace isolation on the Codex runtime:** the runner, or `op.workspace_io` itself, refuses file access outside the declared `fs:` resource keys. Nothing else enforces them there ([permissions](../capsule/permissions.md#gaps-and-conflicts)).
- **A run-start check** that each wired output has the port type of the input it feeds. Today only input names are checked (`PORT_MISMATCH`).
- **The author kit, the catalogue export, and a generator** that writes `make_capsule.md` from the Declaration.
- **B1's "allowed-capsule list in the policy"**: the [policy](../schemas/policy.md) has no such section. Remove it from [B1](../b1-design.md) or define it. With change 5, M1 does not need it.

## Gate verdicts

**Needs agreement** with the Verifier ([PRD review](prd-review.md) point 1). PRD 4.3 names three verdicts, which equal the schema's `decision`. The Verifier brief names five. If the five are adopted, each is derived from existing records, with changes 2 and 3:

| Verdict | `decision` | Derived from |
|---|---|---|
| `PASS` | `pass` | no output Artifact has `issues` |
| `PASS_WITH_KNOWN_LIMITATIONS` | `pass` | an output Artifact has `issues` (change 2). Not from labels: at M1 every judged pass carries `judge_unmeasured` |
| `FAIL` | `fail` | a check returned `fail` |
| `ENVIRONMENT_BLOCKED` | `blocked` | the Observation's reason is owned by `runtime` (change 3) |
| `ESCALATE_TO_HUMAN` | `blocked` | any other `blocked`: a capsule crash, a refusal, or a check the judge could not decide |

Every halting verdict halts the run, as `FAIL` and `BLOCKED` do in PRD 4.3, so five verdicts change what the developer sees at triage, not what the run does.
