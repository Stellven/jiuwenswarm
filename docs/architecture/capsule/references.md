---
type: reference
tags: [capsule, reference]
---

> Research rationale index. Earlier paper figures and future mechanisms are historical context, not current M1 acceptance or runtime guarantees. Use [frozen coverage](../prd/coverage.md) and [current decision owners](../authority.md) for coding. Verify primary paper evidence before reusing numerical claims in a presentation.

# References

The papers and designs Capability Capsule draws on. Every cited paper was read in full; the numbers, pages and caveats are kept in the CC paper ledger. Each row says what CC took from it and where it is used.

## Papers

| Paper | arXiv | What CC takes from it | Used in |
|---|---|---|---|
| Beyond Task Completion (the conformance gap in tool-evolving agents) | 2604.00392 | 215 of 222 self-built tools failed every held-out test of their own job while running cleanly: admission must test the declared job, and running without error is never evidence | [why](why.md), [RSI](rsi.md) |
| CoEvoSkills | 2604.01687 | unverified self-generated skills barely beat none; with a separate verifier, 71.1%. Verification is the value of self-generation | [why](why.md), [RSI](rsi.md) |
| Darwin Gödel Machine | 2505.22954 | an agent removed the logging its checker read: the metric cannot be the gate, and the referee is protected | [why](why.md), [RSI](rsi.md), [trust](trust.md) |
| Alita-G | 2510.23601 | specialised agents with tool retrieval win, and an unmanaged library decays (coverage 1.00 to 0.51 as tools grow) | [generalist](generalist.md), [library](library.md) |
| More Skills, Worse Agents? | 2605.24050 | pass rate falls 0.21 at 202 skills, largely from picking a look-alike: selection must be strict before a model ranks | [why](why.md) |
| Contract2Tool | 2606.07904 | a contract filter reached 0.980 success on 2,528 tokens, against 26,172: declared contracts are cheaper and better | [why](why.md) |
| Don't Offer What Can't Be Done | 2608.01050 | preconditions checked before offering remove 59.1% and 90.5% of description tokens; one evaluator for filter and dispatch | [why](why.md), [Declaration](fields.md) (`needs.when`) |
| SkillFuzz | 2607.02345 | skills that pass alone drift plans together (4.7% with one, 66.5% with five); contract-guided MCTS finds risky sets, 80.6% confirmed | [library](library.md#eligibility-and-failure) |
| Skill Drift Is Contract Violation | 2605.10990 | given the failed contract, one-round repair of drifted tools rose from 10% to 78%; no false alarms over 599 cases. That each dependency states its purpose is CC's design, built on this | [trust](trust.md), [RSI](rsi.md) |
| AllocBench | 2607.23332 | models commit to building at first sight 85 to 99% of the time: the decision to build is separate from building, and recurrence drives a build | [RSI](rsi.md) |
| The Blind Curator | 2607.07436 | a biased judge silently stops retirement; deterministic checks and a judge catch different defects: audit the judges | [library](library.md), [observability](observability.md) |
| When Self-Evolution Backfires | 2608.05810 | removing the gate cost 8 points; clean-up won back only 1.7 of 12.3: gate first, clean later | [library](library.md) |
| Library Drift | 2605.19576 | harsh retirement falls below the no-skill floor; a cap on the active set controls variance | [library](library.md) |
| Cognitive Admission Control (consequential actions in agentic systems) | 2609.16313 | typed admission outcomes: an unknown defers, only a violated check rejects | [library](library.md#admission-the-only-way-in) |
| Cordis | 2608.25512 | spatiotemporal composability: composing capabilities in space and time, and the inside/outside boundary | [composition](composition.md#spatiotemporal-composability) |
| SkillWeaver | 2504.07079 | skills practised before admission | [RSI](rsi.md) |
| SkillDAG | 2606.03056 | typed relations between skills; edits that keep the set monotone | [library](library.md) |
| Agent Contracts (resource-bounded autonomous agents) | 2601.08815 | budgets as part of a contract | [Binding](../schemas/binding.md) (`budget`) |
| Runtime enforcement for reliable autonomous agents | 2602.22302 | enforcing declared limits at run time | [permissions](permissions.md) |
| GraSP | 2604.17870 | prior art on structured skill planning | [Symphony](symphony.md) |
| RelAIBuild | 2606.26924 | prior art on lineage and taint across builds | [library](library.md) |
| CostBench | 2511.02734 | cost as a measured property, not an authored one | [observability](observability.md) |
| Self-evolving agents survey | 2507.21046 | every system freezes something; the claim is what it checks | [RSI](rsi.md) |

## Design inspirations

| Source | What CC takes from it | Used in |
|---|---|---|
| NVIDIA TensorRT | layer fusion: parts that always run together, once proven, become one faster unit; the idea behind A-B and fused AB | [composition](composition.md) |
| openJiuwen Symphony (`flow`) | fingerprinting real results each run; the merge algorithm (qualified edges, grouping only successful edges, versioned packs) | [Symphony](symphony.md), [observability](observability.md) |
| Cordis hyper-plugin framework | spatiotemporal composability; a capsule as a declared plugin | [composition](composition.md#spatiotemporal-composability) |
| Operating systems, package managers, restarts (VS Code window reload, Windows update restarts) | a separate layer frees resources and resolves dependencies; restarting is an accepted way to apply changes. Why mid-run install and uninstall come last | [composition](composition.md#spatiotemporal-composability) |
| Protocol Buffers | never add a required field: new fields are optional, old data stays valid; the policy, not the schema, tightens | [checked and unchecked](stages.md), [invariants](../schemas/invariants.md) |
| C++26 contracts | a contract can be ignored, observed or enforced; CC's unchecked, labelled and blocking levels | [trust](trust.md) |
| npm lockfile integrity, Bazel content-addressed storage | code and dependencies pinned by hash; the same bytes stored once | [library](library.md), [Declaration](fields.md) |
| Git | append-only history, each version naming its parent: a linked list that branches into a tree | [library](library.md#tests-and-lineage) |
| Google Binary Authorization, SLSA provenance | a Verdict as an attestation checked at bind time, never re-tested; a Binding as provenance of what ran | [Verdict](../schemas/verdict.md), [Binding](../schemas/binding.md) |
| Kubernetes admission control and CEL | one admission gate with typed rules and reason codes | [library](library.md#admission-the-only-way-in), [policy](../schemas/policy.md) |
| kube-scheduler | filter, then score: strict rules rule out, then a model ranks | [Symphony](symphony.md) |
| Android permissions | declared permissions a user or policy grants, not assumed | [permissions](permissions.md) |
| Kubernetes StatefulSet | stable identity and ordered handling for stateful parts | [Declaration](fields.md) (`state_kind`) |
| MCP, A2A | how tools and remote agents are reached today; CC adds what they leave out: effects and admission | [why](why.md), [kinds](capsule.md#kinds-of-capsule) |
| RFC 8785 (JSON canonicalisation), SPDX | how a Declaration is hashed; licence ids | [invariants](../schemas/invariants.md), [Declaration](fields.md) |
