---
type: capsule
tags: [capsule, context]
---

# Why Capability Capsule

> **We cannot check something that claims nothing.**

## The problem

An AI4Research run is a chain: ingest, extract, verify, design, report. Each capability feeds the next. One wrong capability early in the chain makes everything after it wrong too, and the run can still finish green. So a capability must be shown to be right **before** it runs, not discovered to be wrong afterwards.

Today nothing lets us do that:

- **Importing capability is already standard.** MCP declares a tool's name and argument schema, and any client imports it. A2A delegates to remote agents.
- **Nothing declares what a capability promises.** A skill from a marketplace is installed on trust: its author writes it, and users watch what happens. Neither MCP nor A2A models effects. "MCP standardises access; A2A standardises delegation." Neither says whether a capability should be allowed in.
- **Value does not exist without a goal.** "Better", "correct" and "improved" are all relations to something stated. Without a declaration there is nothing to verify against, and so no safe self-improvement either.

## The evidence

| Finding | Source | What it means for us |
|---|---|---|
| 215 of 222 tools an agent built for itself scored 0 on held-out tests of their own capability, while executing cleanly | Beyond Task Completion (arXiv 2604.00392) | self-built tools are mostly broken, and task success does not show it |
| Unverified self-generated skills score 30.7 to 34.1%, against 30.6% with no skills; human-curated 53.5%; co-evolved with a verifier 71.1% | CoEvoSkills | verification is the whole value of self-generation |
| An agent removed its own hallucination-detector logging, despite instructions | Darwin Godel Machine | the metric cannot be the gate; the referee must be protected |
| Library coverage fell from 1.00 to 0.51 as tools grew from 26 to 128 | Alita-G | an unmanaged library decays |
| Performance falls as skills are added (-0.21 at 202 skills), mostly from choosing a look-alike | More Skills, Worse Agents | selection must be strict before a model ranks |
| A contract-first tool reached 0.980 on 2,528 tokens, against 0.775 on 26,172 | Contract2Tool | declared contracts are cheaper and better |
| Not offering what cannot run removed 59.1% and 90.5% of tokens | Don't Offer What Can't Be Done | preconditions pay for themselves |
| Skills that each pass alone push plans off course together: severe drift from 4.7% with one skill to 66.5% with five | SkillFuzz | sets must be screened; see [library](library.md) |
| Knowing a dependency's purpose raised successful repair of drifted tools from 10% to 78% | Skill Drift | a dependency should say what it is for, so a builder can update the capsule when it changes |
| Given the choice, models build a new tool at first sight 85 to 99% of the time | AllocBench | deciding to build must be separate from building |

Three levels, one lesson: self-built tools are broken, unverified skills are worthless, and agents break the gate. Each is fixed by a declaration checked by something the builder cannot change.

## Declared, not observed

Other systems observe: they fingerprint what a capability did and learn from outcomes. CC declares first, because **a declaration can be verified and found wrong**. An observation with no stated target measures nothing.

| | Observed only | Declared, then observed |
|---|---|---|
| First check | after use | before use |
| The reference | task success | the declaration |
| A wrong capability | found after it has done damage | refused at admission or stopped at the gate |
| Improvement | toward whatever succeeded | toward a stated promise, with the parent's tests |

Neither alone is enough: CC declares first, then observes every call forever.

## What openJiuwen is missing

openJiuwen already has the engine: a workflow runtime, tool cards, a permission engine, Symphony's index and planner. What it lacks is the column that says what each capability promises. Verified in agent-core at `e23806c1`:

- no effects, preconditions or guarantees on any tool, skill or agent spec;
- no version on any spec, and no hash on any load path;
- no persistent record of what was installed, and no lineage;
- no check before a call that is keyed on the capability; the permission engine sees only the tool name and arguments;
- MCP annotations are dropped, and the workflow tool path skips the tool-call rails.

"The missing column is the schema. The engine is largely there." How CC plugs into it: [Symphony](symphony.md) and [permissions](permissions.md).

## Where CC is going

**Now:** a schema for our own system. Every capability the system uses is declared, checked, pinned and improved the same way.

**End vision:** a library seeded with many capsules, each growing a tree of versions, composed and taken apart as needed (spatiotemporal composability), with every use recorded for RSI.

**Later:** a user installs a tool, skill or MCP server from anywhere. It goes through an isolated verification cycle and comes out as a capsule. Capsules can then be shared through stores or repositories, each carrying its Declaration, checks and Verdict as evidence of what it does and how well.

## What CC is not

- Not a runtime or a framework: CC runs nothing. It is a schema plus the rules for it, used by [tools](tools.md).
- Not a model router: selection picks capsules, never models.
- Not a guarantee of correctness in every case, of safety for every combination, or of undoing emissions. It makes each promise checkable, and each failure attributable.
