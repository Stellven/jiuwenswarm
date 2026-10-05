---
id: capsule.references
type: reference
level: detail
status: proposed
provides: [capsule.references]
depends_on: [why.md, trust.md, rsi.md, library.md]
tags: [capsule, reference]
prd: []
prd_note: bibliography of borrowed external patterns, no PRD clause
---

# References

Borrowed patterns only. Papers are context, not acceptance evidence; verify figures before quoting them.

| Source | What CC takes from it | Used in |
|---|---|---|
| Beyond Task Completion (arXiv 2604.00392) | running without error is no evidence; admission tests the declared job | [why](why.md), [RSI](rsi.md) |
| CoEvoSkills (2604.01687) | self-generation is only worth what a separate verifier adds | [RSI](rsi.md) |
| Darwin Godel Machine (2505.22954) | the metric cannot be the gate; the referee is protected | [trust](trust.md#referees) |
| Skill Drift Is Contract Violation (2605.10990) | each dependency states its purpose so a builder can repair | [RSI](rsi.md) |
| AllocBench (2607.23332) | the decision to build is separate from building | [RSI](rsi.md) |
| Cognitive Admission Control (2609.16313) | typed admission outcomes: unknown defers, only a violated check rejects | [library](library.md) |
| Protocol Buffers | never add a required field; the policy tightens, not the schema | [stages](stages.md) |
| npm lockfiles, Bazel, Git | pin by hash; append-only version history | [Declaration](fields.md) |
| Binary Authorization, SLSA, Kubernetes admission | a Verdict is an attestation checked at bind time; a [Binding](../schemas/binding.md#term-binding) is provenance; one admission gate with typed [reason codes](../schemas/policy.md#term-reason-code) | [Verdict](../schemas/verdict.md), [Binding](../schemas/binding.md) |
| MLflow Model Registry, Temporal workflow history, METR reward hacking | version/alias split; durable progression; referee isolation | [library](library.md), [nodes](../system/nodes.md), [RSI](rsi.md) |
