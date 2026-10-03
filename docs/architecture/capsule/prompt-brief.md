---
type: capsule
status: draft
version: 1
owner: muk
sources: [runner.md, authoring.md, gate-capsules.md, ../m1/requirement-capsule.md, ../PROCESS.md]
provides: [cc.prompt_brief]
consumes: [cc.declaration, cc.run_plan]
depends_on: [runner.md, authoring.md, gate-capsules.md]
tags: [capsule, prompt, handoff, m1]
---

# Prompt brief: what architecture hands to the prompt layer

Architecture does not write prompts. A later layer turns this design into the files a model follows (`SKILL.md`, references, gate rubrics). This page says where the line is, and what every model-backed capsule page must give that layer so it can work without guessing.

## Who decides what

| Architecture fixes (do not change in the prompt layer) | The prompt layer writes |
|---|---|
| Ports, types and their schemas, `issues` codes | `SKILL.md` text and the worked example |
| The deterministic and reference checks, and what each one means | reference files the skill reads (tables, rubrics marked mutable) |
| The prompt envelope, reply format and parsing ([runner](runner.md#kind-handlers)) | the recorded-reply fixtures for tests |
| Effect class, budgets, turn limit, which capsules it may call | the wording of gate rubrics, inside the criteria the run plan names |
| What RSI may change (`evolution.may_change`) | nothing outside that list is touched by RSI |

## What the runner already does

Do not repeat these in a skill. The runner adds them to every call.

- It builds the whole prompt: the skill files, pinned `prompt_section` text, each input, the tool list, and a REPLY block with the output schema.
- The reply must be one JSON object: `outputs` with exactly the output port names, plus optional `issues`, or one `call`. Code fences are stripped. Any other shape ends the call with `CAPSULE_ERROR`. **There is no retry**, so the skill must make the format easy to follow.
- A skill gets at most `runner.max_skill_turns` model turns (proposed: 8) and its time budget. Every body file must be UTF-8 text. `runner.max_inline_file_bytes` limits only `file` inputs and nested `file` outputs shown in the prompt, not body files.
- The model hint comes from `SKILL.md` front matter (`model`). A change of model is a new version.

## The brief every model-backed capsule page carries

Each capsule page that has a model call adds a section named **Prompt brief** with these rows. Rows that do not apply say "none".

| Row | What it gives the prompt layer |
|---|---|
| Job | one sentence: what the output is for, and what it must not decide |
| Inputs | each input port, what it holds, and how the skill should use it |
| Output | each output port and what every field means, by link to the type page |
| Rules | the deterministic checks, in plain words, so the skill satisfies them first time |
| Grounding | what must be quoted or cited from the input, and what may never be invented |
| Gaps | what to do when information is missing: use a default, raise an issue code, or leave absent. Name the code |
| Issue codes | each code, and when to raise it |
| Tools | the capsules it may call, and when a call is worth making |
| Must not | forbidden behaviour: run commands, change scope, pick a solution, set a threshold |
| Examples wanted | the cases the worked example and fixtures must cover, including one that should raise an issue and one that should fail a check |
| RSI surface | the files RSI may rewrite, and the files that stay fixed |
| Done when | the fixtures that must reproduce the expected output, and the checks that must pass |

[`requirement_capsule`](../m1/requirement-capsule.md) already holds most of these rows spread over its sections. The brief gathers them in one place.

## Gate capsules

A gate capsule's rubric is also prompt text, pinned by hash in the run plan. The gate pages ([intent](../m1/intent-gate.md), [brief](../m1/brief-gate.md)) already hold the whole draft of `SKILL.md` and each rubric. The prompt layer may refine the wording, but not the criteria, the three answers or the quote rule. A gate's brief is its page. It adds:

- the criteria it judges, with the step check id for each;
- what `pass`, `fail` and `unknown` mean for each criterion;
- the evidence it may read, and the evidence it may not;
- the rule that a criterion it cannot evaluate is `unknown`, never `pass` (INV-8);
- the rule that it never judges its own work (the policy rule "no self-judging", [policy](../schemas/policy.md)).

The pattern is [gate capsules](gate-capsules.md).

## Rules for the prompt layer

1. Do not restate a schema or a check in the skill. The envelope shows the schema, and the check code is the authority.
2. Name no workflow step, and no model, in the text. A capsule says what it does, not who calls it.
3. Put the worked example in `references/`, so RSI can change it without touching the skill.
4. Record fixture replies from a real run, then replay them in tests. A person other than the writer approves the fixtures (INV-9, INV-10).
5. Any change to any file is a new `decl_hash`. It goes through admission again.

## Which capsules need a brief

Every capsule of the [M1 run plan](../m1/pipeline.md) whose kind is `skill`, and every gate capsule. Pure tools and pinned helpers have no prompt. Briefs written so far: [`compile_brief`](../m1/requirement-capsule.md#prompt-brief) and [`select_opportunity`](../m1/screening.md#prompt-brief). The intent and brief gates carry their text on their own pages. Hypothesis, the POC builder, evaluation and the report writer are provisional pages, so their briefs wait until those pages are firm. The [screening gate](../m1/screening-gate.md) has not been checked for its own text.
