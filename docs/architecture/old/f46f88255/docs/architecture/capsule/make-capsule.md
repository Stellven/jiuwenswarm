---
type: capsule
status: draft
tags: [capsule, draft, guide]
---

# `make_capsule.md`: the readable contract

> **Draft, not yet approved.** What a capsule's `make_capsule.md` looks like, and how it relates to the Declaration.

`make_capsule.md` is the PRD's name for a capsule's contract. In CC it is the **readable form of the [Declaration](fields.md)**. People, reviewers and the Verifier's tier 2 read it.

**The Declaration (`capsule.json`) is the source; `make_capsule.md` is generated from it.** The author kit writes it (M13 in [M1 architecture](../archive/m1-architecture.md)), and nobody edits it by hand. So the readable and the checked contract can never disagree.

## Where it sits in a capsule folder

```
screening_capsule/
  capsule.json          the Declaration: the source, checked by admission
  make_capsule.md       generated from capsule.json; not hashed, never edited by hand
  SKILL.md              the skill the model follows, ported from assessment-screening
  references/rubric.md  the scoring rubric, ported
  checks/screening.py   the code behind its deterministic checks
  tests/cases.json      its test cases, submitted in the Candidate
```

`make_capsule.md` is not in the capsule's `body`. It shows `decl_hash`, and a file that shows the hash of a list containing itself cannot be hashed. It can always be generated again from `capsule.json`.

## What each section comes from

| Section | From the Declaration |
|---|---|
| front matter | `identity.name`, `identity.kind`, the computed `decl_hash` and `interface_hash`, `evolution.rsi` |
| What it does | `identity.summary` |
| Inputs, Outputs | `ports.inputs`, `ports.outputs`, each `value_schema` by URI and hash |
| Acceptance rules | `guarantees.checks`, split by `anchor`: tier 1 (`deterministic`, `reference`) and tier 2 (`judged`) |
| Needs | `needs.when`, `needs.external`, `needs.network`, `needs.resources.timeout_s` |
| Changes | `changes.effect_class`, `changes.effects` |
| RSI | `evolution.rsi`, `evolution.may_change`, `evolution.notes` |
| Files | `identity.body` or `identity.carrier`, with hashes |

Optional fields that are absent are left out, not shown as empty.

## Example: `screening_capsule`

````markdown
---
name: research.screen_ideas
kind: skill
decl_hash: 7c1e...
interface_hash: 52aa...
rsi: propose
generated_from: capsule.json
---

# research.screen_ideas

## What it does

Score candidate research ideas on a multi-dimensional rubric and choose one to pursue.

## Inputs

| Port | Type | Required | Meaning |
|---|---|---|---|
| `idea_set` | json (`payloads/idea_set.schema.json`, 3b09...) | yes | the candidate ideas, each with sources |
| `research_brief` | json (`payloads/research_brief.schema.json`, e41d...) | yes | the question, scope and limits the ideas must serve |

## Outputs

| Port | Type | Checked by |
|---|---|---|
| `scored_ideas` | json (`payloads/scored_ideas.schema.json`, 9a7f...) | `scores_cover_ideas` |

## Acceptance rules

**Tier 1: programmatic**

| Check | Passes when | Runs at |
|---|---|---|
| `scores_cover_ideas` | every idea in `idea_set` has one score entry, with every rubric dimension | admission and every call |
| `chosen_in_scores` | `chosen_id` names a scored idea | admission and every call |
| `brief_limits_respected` | the chosen idea's compute needs fit `research_brief.compute_limits` | admission and every call |

**Tier 2: judged by the verifier**

| Check | Passes when | Runs at |
|---|---|---|
| `rationale_grounded` | the rationale for the choice follows from the scores and cites the ideas' sources | every call |

## Needs

- **Before a call:** `idea_set` has at least one idea.
- **Calls:** nothing.
- **Network:** none.
- **Time budget:** 300 s.

## Changes

- **Effect class:** `pure`. It changes nothing outside its output.

## RSI

- **RSI may:** propose a new version, which waits for a person.
- **RSI may change only:** `files:SKILL.md`, `files:references/rubric.md`.
- **Notes for a builder:** the novelty dimension is the weakest; keep the three dimensions the PRD names.

## Files

| Path | sha256 |
|---|---|
| `SKILL.md` | 1f0c... |
| `references/rubric.md` | 88d2... |
| `checks/screening.py` | c4e9... |
````

The matching `capsule.json` holds the same facts in the field layout on the [Declaration](fields.md) page. The generator writes each table row from one field.

## Rules for the generator

- **One direction only:** from `capsule.json` to `make_capsule.md`, never back.
- **Fixed section order:** the order above, so capsules read alike.
- **Stable output:** the same Declaration always produces the same text, so a diff shows only real changes.
- **Refuse an invalid Declaration:** the generator runs the author kit's checks first, and writes nothing if they fail.
