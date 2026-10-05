# Runtime and improvement

[Start here](README.md) · Specified design · Crash and provider tests pending

## Production authority and normal sequence

- The supervisor validates the plan, freezes the library/configuration/policy closure and owns dispatch. The [runner](../../capsule/runner.md) enforces a Binding, validates ports, reserves call budgets and captures execution. Capsules cannot choose their successor.
- The [model bridge](../../system/model-auth.md) wraps Codex behind a provider interface. Production uses the static configured route; experimental routing selects an allowed endpoint inside a call, not a capability or workflow successor.
- Work output and capture commit first. [Gate host](../../capsule/gate-host.md) evaluates the evidence under a pinned profile and persists Verification through the trusted writer. The supervisor commits release before dispatching the next node.
- Advancement requires committed `PASS` or `PASS_WITH_KNOWN_LIMITATIONS` with `routing_action: ADVANCE`, plus the release record. A passing calculation whose durable save fails cannot release work. See [lifecycle](../../system/lifecycle.md).
- Scientific `PASS`, `FAIL`, `INCONCLUSIVE` and `CONDITIONALLY_ACCEPTABLE` describe research results, not infrastructure permission to advance. A valid negative result can reach a report. See [evaluation](../../m1/evaluation.md).

## Failure and recovery

- Stable duplicate request IDs reuse committed results or report in-progress state; changed bytes conflict. Model/effectful calls do not silently repeat after uncertain outcomes.
- Timeout, cancellation, invalid inputs, denied effects and persistence failures halt the affected attempt and retain safe evidence. Attribution uses the [reason registry](../../schemas/policy.md), not a different error vocabulary per capsule.
- Recovery inspects committed state: reuse work evidence, reevaluate a missing Gate, reuse a committed decision, or dispatch from an existing release. Explicit environment/partial-effect remediation may create an attempt under unchanged pins. Changed inputs, implementation, policy or configuration require a new run. [Lifecycle](../../system/lifecycle.md) and [storage](../../system/storage.md) own exact rules.

- Screening with no eligible card records `NO_ELIGIBLE_OPPORTUNITY` and halts before Hypothesis for human review; it does not create a successful empty card. See [Screening](../../m1/screening.md).

Generated from [information flow](../../system/information-flow.md):

<!-- generated:showcase-recovery -->
```mermaid
flowchart TB
    START["Validate intake, profiles, references and isolation"]
    CALL["Reserve dispatch and invoke pinned CC"]
    SAVE["Persist output, Observation and required capture"]
    GATE["Evaluate deterministic checks and applicable verifier criteria"]
    VSAVE["Persist Verification"]
    PASS{"Committed routing_action ADVANCE?<br/>PASS or PASS_WITH_KNOWN_LIMITATIONS"}
    RELEASE["Persist release for exact run, step and attempt"]
    NEXT["Dispatch successor from committed authority"]
    HALT["Halt: preserve partial evidence and missing-record reason"]
    HUMAN["Explicit human recovery or new run"]
    REC["Reconcile committed records before any re-execution"]
    START -->|"valid and supported"| CALL
    CALL -->|"work complete"| SAVE
    SAVE -->|"publication committed"| GATE
    GATE -->|"computed decision only"| VSAVE
    VSAVE -->|"committed decision"| PASS
    PASS -->|"yes"| RELEASE
    RELEASE -->|"committed"| NEXT
    START -->|"missing input, bad config or unsupported isolation"| HALT
    CALL -->|"timeout, cancellation, duplicate conflict or uncertain effect"| HALT
    SAVE -->|"store or mandatory capture failure"| HALT
    GATE -->|"predecision invocation unavailable"| HALT
    VSAVE -->|"save fails, even after computed PASS"| HALT
    PASS -->|"no"| HALT
    RELEASE -->|"save fails"| HALT
    HALT --> HUMAN
    HUMAN --> REC
    REC -->|"committed result and decision reused"| PASS
    REC -->|"Observation committed but Verification absent"| GATE
    REC -->|"valid committed release reused"| NEXT
    REC -->|"human-approved environment or reviewed partial-effect retry, unchanged pins"| CALL
    REC -->|"changed task, input, policy or config"| START
```
<!-- /generated:showcase-recovery -->

## Admission, RSI and activation

- [Admission](../../capsule/admission.md) always checks declaration integrity, hashes, closure and permissions before the selected provider. Tested admission records checks actually executed. Puppet admission allowlists exact developer-selected hashes with `exempt` assurance; it cannot invent certification or runtime Gate passes.
- [Library](../../capsule/library.md) keeps version, assurance and active alias separate. A candidate can be admitted but inactive; manual activation changes future snapshots, not a frozen run.
- [Offline RSI](../../capsule/rsi-engine.md) uses the private [fixture oracle](../../capsule/fixture-oracle.md), bounded session/lifetime budgets and lineage evidence. Permitted changes stay inside the target's frozen contract. It cannot modify schemas, referee, acceptance policy, permissions, live DAG or active aliases.
- The RSI search loop and final evaluation use separate reservations. Loop calls cannot consume the final evaluation reservation. Read the oracle owner for exact allocation and cross-session limitations.

## Experimental authority

Approved component and Gate ablations use a distinct track-scoped authority: `experimental_gate_evidence` records NOT_RUN or PARTIAL, and `experimental_advance` authorizes the permitted experimental transition. A skipped check never becomes a passed Verification. Authentication, confinement, schema validation, raw capture and storage integrity cannot be disabled. [Experiments](../../system/experiments.md) owns approval, evidence, replacements and promotion boundaries.

<!-- generated:showcase-experiments -->
```mermaid
flowchart LR
    I[Local entry] -->|track=production| F[Fixed plan / static Codex]
    I -->|track=isolated_experiment| E[Experiment feature validator]
    E --> C[Dynamic compiler adapter]
    C -->|research_brief| P[Leader planner]
    P -->|run_plan| V[Deterministic validator / freeze]
    V --> R[Governed runner]
    F --> R
    R -->|ordinary governed step| G[Real Gate / durable release]
    R -->|approved Gate ablation| X[NOT_RUN or PARTIAL evidence / experimental advance]
    O[Offline RSI controller] -->|Candidate only| A[Admission]
    A --> H[Human activation]
```
<!-- /generated:showcase-experiments -->

## Planner and deferred interaction analysis

- [Planner](../../system/planner.md) is an isolated orchestration service using the configured Codex bridge, default GPT-6.1 Sol. It proposes a typed plan from a validated task and admitted library snapshot.
- The deterministic validator checks exact schemas, closure, cycles, reachability, bounds, permissions, required Gates and objective coverage. Only a committed valid proposal can freeze and dispatch. Production validates its fixed plan without a model proposing it.
- Invalid proposals preserve structured findings and cannot dispatch. The experimental policy bounds clarification; no live replanning or unrestricted delegation is introduced.
- **Deferred:** SkillFuzz analysis of how CC sets interact. Planned structural/failure fixtures remain; probabilistic interaction screening is not a current admission, planning or handoff prerequisite. No interaction campaign is claimed to have run.

The durable-history, policy/enforcement and version/alias precedents are explained at [lifecycle](../../system/lifecycle.md), [Gate host](../../capsule/gate-host.md) and [library](../../capsule/library.md).

[Next: data and permissions](data-and-permissions.md)
