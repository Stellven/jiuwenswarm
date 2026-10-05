---
type: home
status: draft
tags: [process]
---

> **Draft, not yet approved.** The standing procedure for building this vault. Written 2026-10-01.

# How the architecture is built

**The goal.** Turn the [frozen PRD](../product/SOURCE_FREEZE.md) into API-level design that separate builders can implement and connect. [Architecture policies](policies.md) govern source precedence, minimal modules, AI review and handoff releases. `locked` records Muk's approval; checked contracts may be design inputs before approval.

**Decisions and precedents.** Every architecturally significant choice is recorded in the [decision ledger](decisions.md) with its primary precedent, the exact pattern borrowed, local rationale, owner, affected contracts, validation state, replacement trigger and migration boundary. A cited system is precedent, not proof and not automatically a dependency.

## What a page's status means

| Status | Means | Who sets it |
|---|---|---|
| `draft` | written, not yet through the loop | the author |
| `checked` | through the loop: the lint passes, the canary agrees or a review's findings are applied, and every dependency it relies on is `checked` or `locked`. It **should** be complete; what is still open is listed in [open issues](open-issues.md) | the architect, after the loop. The lint refuses `checked` while a dependency is still `draft` |
| `locked` | `checked`, and approved by Muk. It changes only through the change order below. Locking is an approval state, not a prerequisite for other architecture work to consume the checked contract | Muk |
| `blackbox` | legacy status, retired from the active coding path. Every current responsibility has a concrete design and failure outcome; unrun security evidence remains a validation obligation | history only |

**A contract change reopens its consumers.** Recheck the owner and every transitive producer, consumer, Gate, run-plan, seam and diagram page relying on the changed field, meaning, error or effect. Record that set before editing. [Validation obligations](open-issues.md) track missing runtime proof; [system boundaries](system/blackboxes.md) links concrete designs.

The banner under the front matter says the same: **Checked, not yet approved** or **Draft**.

## Where things live

- **Design:** this folder, jiuwenswarm `docs/architecture/`. **PRD:** `docs/product/`, verbatim, indexed in its README. Notes elsewhere (obby) are never the design.
- **Upstream material found anywhere else** (a teammate's PRD or design) is copied verbatim into `docs/product/` or a workstream folder here the same day, and its seams with CC are written in [seams](seams.md).
- **One concept per page, as big as it needs to be.** There is no size limit. Split a page only when it holds separable concepts, or when keeping two parts in one file makes them restate each other, so there are two sources of truth to keep in sync. A split page becomes a folder with an index. Muk's direction, 2026-10-02.
- **Mermaid is the graph format,** because machines can read it. [graph.md](graph.md) is generated from front matter; never edit it.

- **Major architecture lives in architecture pages, never only in a proposal or a note.** Build order, observability, lifecycle, configuration, the capsule set and the decisions behind them each have an owner page in this folder. A proposal page records only the delta and the reasoning, links to the owners, and is replaced by edits to them on adoption. Muk's direction, 2026-10-02.
## Working agreements

Kept here so they live with the design, not in anyone's notes.

- **Provenance:** follow [clean release policy](policies.md#provenance-and-clean-releases). A commit does not imply locked pages or runtime acceptance.
- **Fetch before every push.** Resolve compatible documentation changes against the frozen sources; preserve and record semantic conflicts. Never force-push or overwrite unrelated work.
- **No `.pptx` in the repository.** A deck becomes Markdown with Mermaid.
- **Received files stay verbatim.** [Policies](policies.md) own source precedence and provenance; architecture interpretations link the frozen receipt and never rewrite it.
- **Commit messages** have a simple descriptive title and no body.
- **Reviews** normally use fresh AI contexts and exact source/contract evidence. No particular model is required. Independent producer and consumer reviews may run concurrently; the author resolves source-verified findings. People receive a concise decision brief.
- **Language:** short sentences, active voice, main point first. Software jargon is fine; define a coined term. No em dash.

## The order for changing anything

A change flows from its owner outward. Never edit a consumer before the owner.

1. **Record** the change in [decisions](decisions.md): what, why, precedent, replacement trigger and which pages consume it. A schema or API has one owning page; list downstream pages and seams that consume that definition. Put only unresolved product conflicts or implementation-validation facts in [open issues](open-issues.md). For a checked contract change, identify its full dependent recheck set before updating pages.
2. **The owner page:** the one page that defines the thing (a `types/` page, a `schemas/` page, [fields](capsule/fields.md), [policy](schemas/policy.md)). The table [where every shared datatype is defined](types/types.md#where-every-shared-datatype-is-defined) names it.
3. **Lint** until it prints `ok`.
4. **Consumers:** update them to **link** to the owner, never to restate it.
5. **Module, node and capsule pages,** then [seams](seams.md). Before separate implementers build connected modules, their pages must reference the same checked type/API and the seam canary must agree.
6. **Indexes:** [README](README.md), the "where defined" table.
7. **Notes last.**

## Rules for a good schema

| Rule | Prevents |
|---|---|
| Every shared datatype has one owning page and immutable released versions; each binding pins its exact version | copies drifting apart; several versions in force at once |
| One identity per object, one field name for it everywhere | the same object under two ids |
| No task, step or run id inside a reusable schema (INV-7) | values that only work in one run |
| Closed core plus one `ext`; consumers read only declared fields | checkers and schemas that disagree on field names |
| Every field in the type grammar, compiled mechanically, with a validating example | schemas that do not match the code |
| A rule written only in prose is not enforced: make it a check | "always", "never" and "at least" that nothing checks |
| Unknown never passes (INV-8); no default status | gates that pass what they cannot evaluate |
| Refer, never copy (INV-5, INV-6); one writer per record kind (INV-3) | drift between copies; many state surfaces |
| Every promise has a check, written by someone other than the builder (INV-9, INV-10) | a referee that judges itself |
| Every code claim cited `path:line` at a commit | docs that drift from code |
| **One interface, policy-selected profiles.** Different assurance, Gate, retry or execution needs use a named versioned profile behind the same API. A new need creates a profile or schema version, not a call-site exception | special cases that multiply |

**The schema holds; the policy tightens** (INV-17). A field can exist before any tool reads it. As tools arrive, the policy starts requiring and checking more fields. Nobody re-authors a capsule because a new check switched on.

## Fitting existing code

**The reuse ladder.** Try each step in order, and write down which was taken:
1. Reuse an agent-core or jiuwenswarm piece as it is, cited.
2. Map it at a seam, with the mapping written on the owning page.
3. Define it new.

**Every connection to existing code** is a row on [integration](system/integration.md) before it is code, and goes through `cc/adapters/`. Earlier systems, such as AI4Research, are lessons only: a schema stands on its own reasons.

## Review allocation

Use the [bounded agent review workflow](review-workflow.md) for each connected change. Mechanical checks precede agent review; fresh roles receive pinned owners and exact source clauses. Routine reviews are targeted, while handoff reviews cover all five system journeys. Confirm transitive impact before reusing unchanged evidence.

## The area loop

An area may be drafted against an explicitly pinned draft interface; record assumptions and the full recheck set. An area becomes `checked` only after its dependency checks pass. Design drafting does not wait for another person's availability. Pending external inputs use a bounded adapter; specified safety mechanisms carry validation obligations rather than undefined black boxes.

```mermaid
flowchart LR
    S0["0 pick area and pin dependency revisions"] --> S1["1 read frozen source clauses and contracts"]
    S1 --> S2["2 seam inventory: reuse ladder per datatype"]
    S2 --> S3["3 draft: types, then APIs, then node pages"]
    S3 --> S4{{"4 lint ok"}}
    S4 --> S5{{"5 canary: blind derivations agree"}}
    S5 -->|"mismatch: fix the docs"| S3
    S5 --> S6{{"6 fresh source-verified design review"}}
    S6 --> S7["7 apply verified findings, lint"]
    S7 --> S8["8 checked, then Muk may lock"]
    S7 -->|"what remains"| OI[("open-issues.md")]
```

- **Node pages** follow [the node template](system/modules.md), so each can become a Declaration and code directly.
- **Every review finding is checked in source before it is applied.** Recheck changed claims; allow targeted further review when a material disagreement remains. Unresolved acceptance obligations go to open issues with an owner, consequence and expected evidence.
- **The review checklist:** a datatype defined twice; an API whose arguments, return value, errors or records are unstated; a reference to something undefined; a type that does not compile or an example that does not validate; an invariant broken; a PRD sub-feature with no page and no written reason; stale text after a change; control flow outside a capsule or the run plan; a host with stage logic. Reviewers use a fresh context and verify every finding against the PRD and architecture sources. Apply verified findings; record unresolved product decisions in [open issues](open-issues.md).

## The canary

For each seam an area touches, two fresh agents, each with only the vault and no session context, derive the two sides as Declarations. Then:

```text
python _tools/arch_lint.py canary --producer A.json --consumer B.json --wire OUT=IN --external NAME
python _tools/arch_lint.py canary --compare A.json B.json
```

**Any mismatch means the docs are under-specified.** Fix the docs, never a derivation, and run again.

## The overall system diagram

[The overall system diagram](system/diagram.md) is a standing canary. Every module and every datatype that moves between modules is on it. The lint checks:
- every drawn node is in its Nodes table, and the reverse;
- every edge label is a datatype in its Edge labels table, linked to its one definition;
- every payload type is on an edge;
- every capsule of the M1 run plan is drawn.

**Redraw it in the same change** whenever a module, an adapter or a datatype is added, removed or renamed. A part that cannot be drawn is a wrong part. A drawing that does not make sense is a design error, found before any code exists.

## The step back

- **When:** follow the connected-batch and five-journey cadence in the [review workflow](review-workflow.md#cadence-and-journey-rotation), including every shared authority/security change and before coding handoff. This cadence does not wait for a page to be locked.
- **Who:** a fresh reviewer, reading the vault and the PRD without relying on the author’s conclusions. It walks one run end to end, maps every PRD sub-feature to a page, and reads the graph. No particular model is required.
- **Output:** a report in [reviews/](reviews/2026-10-01-system-step-back.md). The loop resumes once every finding has a disposition.

## The lint

`python docs/architecture/_tools/arch_lint.py [--check]`. The old `tundle/tools/architecture_sync.py` now runs it. It checks:
- payload/record field tables and the INV-11 to INV-13 rules; ordinary-service API envelopes use canonical authored JSON Schema under `contracts/` and separate fixture validation;
- links and Mermaid;
- every type page compiles and its example validates;
- no page restates a type's field table;
- no retired name is in use;
- system pages carry front matter;
- `graph.md` is current;

Still to add: lock hashes for locked pages, and `adapters_only` once code exists.

## Seven coding-handoff questions

Every module must link canonical answers for: placement/reuse/process/owner; typed API/files/errors/deadlines/duplicates/cancellation; startup/call/Gate/release/halt/restart; durable writers/correlation/crash recovery/frozen inputs; actual identity/filesystem/network/credentials/IPC confinement; platform/dependency/config/precedence/reload; standalone invocation/observations/failure injection/integration path. [Module map](system/modules.md) indexes these owners; [verification](system/verification.md) specifies invocation evidence. Internal algorithms remain implementation choices. A linked PRD clause without a concrete contract does not establish readiness. Runtime tests and their observed results are supplied later by the coding role.
