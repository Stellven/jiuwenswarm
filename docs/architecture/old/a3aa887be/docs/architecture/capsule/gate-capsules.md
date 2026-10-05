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

## Runtime result being verified

`research.verifier` is a reusable capability capsule. At runtime its bound test checks the result of a node: the task-specific hot-path use of another CC, with concrete inputs, output and captured evidence. Library storage/admission concerns the reusable capability; node Verification concerns that particular application. [Node model](../system/nodes.md#capsule-versus-node) owns the distinction.

## Declaration-derived Gate construction

The bound verification capsule receives the producer capsule's exact Declaration and output/evidence references. A trusted Gate builder derives a test instance from the declared output schema, guarantees/check references, effects, permissions and allowed failure outcomes, together with mandatory host policy. It prepares that instance automatically at binding/freeze and places its Gate invocation immediately after the producer's work call. The Gate checks actual output and capture, not only the Declaration's syntax.

There is one reusable `research.verifier` capsule implementation and one declaration-specific generated test instance for each work Binding. Generated tests are instances/derived artifacts, not a claim that a new independently trained verifier exists for every node. The builder may resolve existing deterministic checks and parameterize the fixed verifier instructions; generated code, if ever used for tests, needs its own validated construction/confinement contract before acceptance. An unsupported declared obligation fails preparation rather than being silently omitted.

Freeze pins the producer declaration hash, generated test hash, verifier version, profile and policy closure. Mandatory safety checks cannot be removed by a producer's Declaration. Gate instructions/body and the bound test instance have zero RSI-mutable components; automatic test preparation is trusted contract compilation, not RSI. A declaration or test-policy change produces new pins and a new comparison cohort. Tests are not recorded as passed until the Gate actually executes against evidence.

Exact Declaration transport, generated test record schema and builder API remain connected contract work. This section defines authority, construction inputs, placement and observable failure behavior at architecture level; it does not alter received PRD text.

## What every gate capsule declares

The verifier declares exactly one `evidence_bundle` input and one `verifier_assessment` output; effect class is read_only or pure, RSI is none, and it has no authority to release a step. It receives only immutable evidence selected by the Gate host and independently authored criteria from the pinned GateProfile. The producer cannot choose criteria. Freeze pins verifier declaration, profile, rubric/check closure and model-route configuration.

The host invokes the verifier only after mandatory Tier 1 checks pass. The verifier returns per-criterion assessment, rationale and exact evidence quotations. Deterministic verifier checks require every requested criterion exactly once, no extra criteria, valid outcome/quote semantics and grounding against the supplied bundle. Malformed, timed-out or unavailable judgment blocks release. The host alone aggregates and persists Verification.

## Stage independence

Intent and requirement capsule call sites have declaration-derived tests and pinned frontend criteria. Their exact revised profile contracts remain to be finalized. The existing Brief, Search, Screening, Hypothesis, POC, Scientific Benchmark, Evaluation and Report criteria remain research capability references; they do not define the complete outer workflow. Sharing the execution mechanism does not share the producer's prompt or weaken stage criteria. Report's Gate precedes mechanical publication. Ordinary helper modules use deterministic checks inside their enclosing stage, avoiding artificial standalone Gates.

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
