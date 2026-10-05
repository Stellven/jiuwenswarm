---
id: capsule.prompt-brief
type: capsule
status: proposed
version: 1
sources: [runner.md, authoring.md, gate-capsules.md, ../capabilities/requirement-capsule.md]
provides: [cc.prompt_brief]
consumes: [cc.declaration, cc.run_plan]
depends_on: [runner.md, authoring.md, gate-capsules.md, ../verification.md]
tags: [capsule, prompt, handoff, m1]
level: detail
prd: [4.1.1, 4.2.1]
---

# Prompt brief: what architecture hands to the prompt layer

PRD: 4.1.1, 4.2.1

> Answers: How does a prompt brief hand a capsule its task text?

Architecture does not write prompts. A later layer turns this design into the files a model follows (`SKILL.md`, references, gate rubrics). This page says where the line is, and what every model-backed [capsule](capsule.md#term-capability-capsule) page must give that layer so it can work without guessing.

## Who decides what

| Architecture fixes (do not change in the prompt layer) | The prompt layer writes |
|---|---|
| Ports, types and their schemas, `issues` codes | `SKILL.md` text and the worked example |
| The deterministic and reference [checks](fields.md#term-check), and what each one means | reference files the skill reads (tables, rubrics marked mutable) |
| The prompt envelope, reply format and parsing ([runner](runner-handlers.md#kind-handlers)) | the recorded-reply [fixtures](../system/test-surfaces.md#term-fixture) for tests |
| Effect class, budgets, [turn](../system/model-bridge.md#term-model-turn) limit, which capsules it may call | the wording of [Gate](../verification.md#term-gate) rubrics, inside the criteria the [run plan](../types/run-plan.md#term-run-plan) names |
| What [RSI](../rsi.md#term-rsi) may change (`evolution.may_change`) | nothing outside that list is touched by RSI |

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

[`requirement_capsule`](../capabilities/requirement-capsule.md) already holds most of these rows spread over its sections. The brief gathers them in one place.

## The verifier and Gate profiles

The verifier's judging instructions are prompt text, pinned by hash. There is one verifier CC ([gate capsules](gate-capsules.md)); each Gate call site supplies criteria through a profile, for example the [intent](../capabilities/intent-compile.md#gate) and [brief](../capabilities/brief-gate.md) Gates. The prompt layer may refine wording, but not the criteria, the three answers or the quote rule. A [Gate profile](../schemas/profiles.md#term-gateprofile)'s brief is its capability page. It adds:

- the criteria it judges, with the step check id for each;
- what `pass`, `fail` and `unknown` mean for each criterion;
- the evidence it may read, and the evidence it may not;
- the rule that a criterion it cannot evaluate is `unknown`, never `pass` (INV-8);
- the rule that it never judges its own work (the policy rule "no self-judging", [policy](../schemas/policy.md)).


## Rules for the prompt layer

1. Do not restate a schema or a check in the skill. The envelope shows the schema, and the check code is the authority.
2. Name no workflow step, and no model, in the text. A capsule says what it does, not who calls it.
3. Put the worked example in `references/`, so RSI can change it without touching the skill.
4. Record fixture replies from a real run, then replay them in tests. A person other than the writer approves the fixtures (INV-9, INV-10).
5. Any change to any file is a new `decl_hash`. It goes through admission again.

## Which capsules need a brief

Every model-backed capsule listed in [capabilities](../capabilities/README.md), whether a Markdown skill or Python tool wrapper, and the verifier itself, needs a prompt brief. `research.compile_intent` is model-backed (compile and repair prompts) and needs a prompt brief for both. Pure tools and pinned helpers have no model prompt. Capability pages define bounded model behavior and grounding; Screening's brief distinguishes its model's internal assessments from its wrapper's public card output. Prompt wording and calibration are downstream work.
