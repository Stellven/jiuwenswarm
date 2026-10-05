---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, gate-host.md]
provides: [cc.gate_capsule_pattern, prompt.gate_judging]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment, cc.declaration]
depends_on: [gate-host.md, runner.md, ../schemas/profiles.md]
tags: [capsule, gate, m1]
---

# Shared infrastructure verifier

M1 admits one `research.verifier` skill. Stage Gate pages own independent criteria profiles, not separate verifier capsules. Fixed shared judging instructions are hashed files of this capability. The scientific evaluator is a separate work capability and never judges its own infrastructure admissibility.

## Count, scope and frozen referee

M1 uses **one semantic verifier capability identity**, `research.verifier`, with multiple stage-specific Gate profiles and invocation sites. The corrected [control flow](../m1/control-flow.md) adds intent/requirement acceptance before planned DAG execution; those profiles require connected contract revision, not additional verifier identities. Every executed work capsule enters its associated Gate boundary before any following work capsule can use the result.

All capsules acting as Gates declare `evolution.rsi: none` and `evolution.may_change: []`: zero RSI-mutable components. RSI cannot change Gate prompts, bodies, dependencies, checks or criteria policies. A human-authored referee revision creates a new pinned comparison cohort. Success-rate reports retain work/referee/profile/fixture/model/protocol pins so an improved capsule is measured against the same referee rather than a moving one. Small fixture suites remain smoke/contract evidence, not a guaranteed statistical success rate.

A Gate failure halts dispatch for the run, including other ready branches; results already committed remain diagnostic evidence. Delivery is ordinary result processing/publication after accepted terminal outputs, not a Gate or work capsule.

## What every gate capsule declares

The verifier declares exactly one `evidence_bundle` input and one `verifier_assessment` output; effect class is read_only or pure, RSI is none, and it has no authority to release a step. It receives only immutable evidence selected by the Gate host and independently authored criteria from the pinned GateProfile. The producer cannot choose criteria. Freeze pins verifier declaration, profile, rubric/check closure and model-route configuration.

The host invokes the verifier only after mandatory Tier 1 checks pass. The verifier returns per-criterion assessment, rationale and exact evidence quotations. Deterministic verifier checks require every requested criterion exactly once, no extra criteria, valid outcome/quote semantics and grounding against the supplied bundle. Malformed, timed-out or unavailable judgment blocks release. The host alone aggregates and persists Verification.

## Stage independence

Brief, Search, Screening, Hypothesis, POC, Scientific Benchmark, Evaluation and Report each have their own pinned independent acceptance criteria. Sharing the execution mechanism does not share the producer's prompt or weaken stage criteria. Report's Gate precedes mechanical publication. Ordinary helper modules use deterministic checks inside their enclosing stage, avoiding artificial standalone Gates.

The evidence and criteria remain data supplied to one verifier implementation, following [OPA policy/data separation](https://www.openpolicyagent.org/docs). A changed referee prompt requires a new admitted verifier version and all stage defect fixtures to be rechecked. A changed stage profile rechecks only that profile and its producers/consumers, then requires a new policy/library snapshot. The immutable M1 referee cannot be edited by RSI.

```mermaid
sequenceDiagram
    participant H as Gate host
    participant R as Check runner
    participant V as research.verifier
    participant S as Store
    H->>R: mandatory type/reference/check assertions
    R-->>H: Tier 1 results
    alt mandatory assertion failed
        H->>S: persist blocking Verification
    else Tier 1 passed
        H->>V: evidence_bundle + pinned stage criteria
        V-->>H: verifier_assessment
        H->>R: validate assessment completeness and quotations
        H->>S: persist aggregated Verification
    end
```

A verifier call uses caller=gate; its assessment validation is performed directly by the host to terminate recursion. This is a role contract, not a runtime Gate bypass for work capsules. Independent invocation and planted-defect fixtures are specified in the system verification catalogue.
