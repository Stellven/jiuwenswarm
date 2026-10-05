---
id: capsule.make-capsule
type: capsule
status: proposed
tags: [capsule, guide]
level: detail
provides: [capsule.make_capsule]
depends_on: [fields.md, toolchain.md]
prd: [4.1.1]
---

# `make_capsule.md`: the readable contract

PRD: 4.1.1

> Answers: What does the readable make_capsule contract say?

`make_capsule.md` is the PRD's name for a [capsule](capsule.md#term-capability-capsule)'s contract. In CC it is the **readable form of the [Declaration](fields.md)**. People and the verifier's [Tier 2](../verification.md#term-tier-2) read it.

**The [Declaration](fields.md#term-declaration) (`capsule.json`) is the source; `make_capsule.md` is generated from it.** The author kit writes it ([toolchain M13](toolchain.md#m13-author-kit)), and nobody edits it by hand. So the readable and the checked contract can never disagree.

## Where it sits in a capsule folder

```
screening_capsule/
  capsule.json          the Declaration: the source, checked by admission
  make_capsule.md       generated from capsule.json; not hashed, never edited by hand
  SKILL.md              the skill the model follows
  references/rubric.md  the scoring rubric
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
| [RSI](../rsi.md#term-rsi) | `evolution.rsi`, `evolution.may_change`, `evolution.notes` |
| Files | `identity.body` or `identity.carrier`, with hashes |

Optional fields that are absent are left out, not shown as empty.

## Example shape

The generated file has the front matter (`name`, `kind`, `decl_hash`, `interface_hash`, `rsi`, `generated_from: capsule.json`) and then these sections in fixed order: What it does, Inputs (port, type with schema URI and hash, required, meaning), Outputs (port, type, checked by), Acceptance rules ([Tier 1](../verification.md#term-tier-1) programmatic [checks](fields.md#term-check) with when they pass and where they run; Tier 2 judged checks and their judge), Needs, Changes, RSI, Files (path and sha256). For `research.screen_ideas`, Inputs lists `idea_set` and `research_brief`, the output is `scored_ideas`, [effect class](fields.md#term-effect-class) is `pure`, and RSI may change only `files:SKILL.md` and `files:references/rubric.md`. Each row is written from one field of `capsule.json` ([Declaration](fields.md)).

## Rules for the generator

- **One direction only:** from `capsule.json` to `make_capsule.md`, never back.
- **Fixed section order:** the order above, so capsules read alike.
- **Stable output:** the same Declaration always produces the same text, so a diff shows only real changes.
- **Refuse an invalid Declaration:** the generator [runs](../system/lifecycle.md#term-run) the author kit's checks first, and writes nothing if they fail.
