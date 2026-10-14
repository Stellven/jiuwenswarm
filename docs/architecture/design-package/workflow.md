# Workflow: planning and execution

**Reading level: human potential.** Question answered: How are accepted requirements turned into governed work and dependencies?

## Establish intent before planning

**Core build scope:** the fixed Compiler Intent + Requirement sequence and their required independent gates produce an accepted `research_brief`; this preparation is mandatory in the core. The admitted planner then proposes a bounded JSON DAG of downstream CCs with objective coverage, typed ports, dependencies and any suggested extra checks. The protected binder independently selects mandatory profiles, validates coverage, ports, dependencies, cycles, permissions and resource feasibility, assigns required checks, and freezes the [`run_plan`](reference/run-plan.md) before research dispatch. An infeasible or rejected proposal halts the run and starts a linked Intention Compiler attempt. There is no silent switch to the static template. The static template is built first and yields the same run plan type ([D26](decision-review.md#d26)). Select the mode before execution. The real governed journey remains Search → Screen → Hypothesis → Builder → Benchmark → Scientific Evaluation → Delivery. See [core build](core-build.md) for scope reconciliation and recorded PRD deviations (D19).

**Required now.** Ordinary intake binds the original request and permitted documents, project assets, and validation data to a run. Reject empty or unreadable required input. Do not fetch undeclared datasets, clone arbitrary repositories, or turn missing evidence into observed facts.

D5 separates Intent and Requirement compilation, with independent verification at each boundary. The Delivery Phase 1 product entry remains bounded and non-interactive: one orchestration request produces the complete Brief without autonomous solution design. The current PRD explicitly leaves internal bounded, non-interactive compiler steps to architecture; their combined time/call limits are frozen. The earlier complete Intention Compiler node exercised only the first; the current complete compiler build must reach accepted Brief. The accepted Research Brief states objectives, scope, constraints, deliverables, and evidence obligations. Preserve ambiguity; a material unresolved requirement blocks readiness. The [Intent/Requirements field contract](reference/intent-and-requirements.md) fixes shared information; protected default policy supplies only authorized missing parameters. A topic with no workable purpose/result halts rather than receiving invented intent. These fixed verification assignments cannot be removed by the planner.

```mermaid
flowchart TB
    Intake[Intake] --> Intent
    subgraph Compiler[Intention Compiler node]
        Intent[Intention work subnode]
    Intent --> IV[Intent checks, verifier subnode and protected gate]
    IV --> Req[Requirements work subnode]
    Req --> RV[Requirements checks, verifier subnode and protected gate]
    RV --> NG[Protected node finalization]
    end
    NG --> Plan[Core bounded planner CC]
    Plan --> Bind
    Bind --> PV[Plan Evaluator Gate]
    PV --> Freeze[Freeze accepted graph]
    Freeze --> Run[Execute research DAG]
    Run --> Out[Expose verified delivery]
    subgraph Legend[Legend]
        Key[Blue: CC work; purple: verification; amber: infrastructure]
    end
    classDef work fill:#E8F0FE,stroke:#2563EB,color:#172554
    classDef verify fill:#F3E8FF,stroke:#7E22CE,color:#3B0764
    classDef control fill:#FEF3C7,stroke:#B45309,color:#451A03
    class Intent,Req,Plan,Run work
    class IV,RV,PV verify
    class Intake,Bind,Freeze,Out,NG control
```

Verification boxes include deterministic checks, a separate verifier invocation, and protected gate application, as specified in [capsules](capsules.md). A clarification or blocking result is recorded through the control plane; headless evaluation returns a blocking status without waiting for interactive input.

Preparation is a protected fixed sequence established by the run-state module before the research graph exists. It gives each enclosing preparation node and its work/verifier subnodes distinct node/subnode/attempt identities, admitted pins, input references, policy and budgets. The same runner and release boundary apply; a pre-freeze invocation is not permission to execute a proposed graph. Freeze authorizes only the later research DAG. This prevents a circular dependency in which the planner would need its own finished graph before it could run.

The [guard design](guard-design.md) defines shared profile resolution for fixed preparation and planned work. The protected binder remains present in both phases; a planner supplies a proposal, never a replacement for binding or independent guard assignment. Preparation templates are bound and checked before dispatch just as later contract templates are; research graph freeze is the later aggregate authorization.

## Planner choice and limits

The accepted Brief is produced first by fixed Compiler Intent and Requirement work with mandatory checks. The core planner then creates a bounded JSON DAG of admitted downstream CCs. Inputs include accepted requirements, a captured admitted-library snapshot, permitted resources, effective policy and limits. The proposal carries objective-to-result coverage, typed ports, dependencies, and optional additional checks. [Plan and node fields](reference/other-contracts.md#planning-and-node-contracts) define the contract. The protected binder independently assigns mandatory profiles and checks, validates requirement coverage, typed-port compatibility, dependencies, cycles, permissions and resource feasibility, and freezes the accepted graph before dispatch. The planner cannot execute generated plan code, grant access, change active library versions, or waive required verification. Invalid or failed planning halts; fallback requires an explicit run mode selected before execution. The retained fixed sequential SwarmFlow runner is a supported fallback mode, not an automatic recovery path.

Generate a bounded set of candidates. The protected binder rejects missing or ineligible capabilities, selected CC versions without an explicit admitted check-bundle association and compatibility evidence, incompatible port meanings, cycles, unbound inputs, denied effects, conflicting shared writes, absent mandatory verification, and exceeded limits; it independently checks requirement coverage and known feasibility before freeze. Binding captures exact CC/bundle pins and adds contract/policy checks to each CC's required bundle; both sources are mandatory. The semantic model sees only the Planner declaration and exact plan output ([D24](decision-review.md#d24)). Coverage against the Brief is a binder check, not a semantic pass. See the [Planner page](reference/capsules/planner.md). No available capability means infeasible planning, not an invitation to invent one.

Rank feasible candidates first by comparable evidence of successful outcomes, then execution time and available cost. Keep sample counts and uncertainty visible. Unknown reliability remains unmeasured, and unknown cost is not zero. The selected planning profile pins the bounded search, comparison rule, conservative defaults and ties. Preserve a fixed reference graph for regression and matched comparisons. A single feasible candidate provides no evidence of optimization.

This is the best candidate found within a declared search budget, not globally optimal planning. A separate logical-operator layer would add binding flexibility but also another representation to reconcile; direct CC bindings provide one inspectable execution boundary shared with the static fallback. Retain objective mappings so later logical planning can lower into that same boundary. Separating graph proposal, dependency dispatch and execution makes their evidence and authority independently inspectable.

## Freeze and unknown future values

**Required now.** Freeze the accepted topology, exact CC and dependency versions, each participating CC's check-bundle version and compatibility evidence, verification profiles, policy, limits, and input references before planned execution. Store Node/subnode contract templates and hashes at freeze; instantiate concrete future-input references against that captured snapshot as predecessor results become accepted. Record the complete bound check plan and final contract identity before dispatch. No active-library or bundle change can alter an existing run, and no post-start contract/check-plan edit is permitted. Future producer outputs are typed references, not already-known values. Freeze does not claim that a hypothesis or measurement exists before its producer runs.

Choose capabilities whose declared input range covers the supported M1 research domain. Use one opportunity and one hypothesis path. The Hypothesis CC establishes and freezes the baseline, validation resource, measurement definitions, success/falsification boundaries, and protocol before POC generation or empirical execution. Downstream work may apply that protocol but cannot edit it after seeing results.

Evaluate preconditions with the same semantics at planning and dispatch. Known false conditions reject a plan; value-dependent conditions remain explicit dispatch obligations. An unsupported hypothesis, missing resource, or false dispatch precondition blocks the run. Do not silently choose another capsule, alter the graph, or create a new protocol. Immutable pins prevent version substitution; current suspension/revocation may still block a pinned version at start or release. Multiple planning epochs remain a future possibility, not M1 behavior.

## Tasks, nodes, and verification

**Required now.** A task groups objectives; a node is a governed objective instance, not a CC call. Protected runtime assembly creates its Node Execution Contract from accepted requirements, fixed or approved planned bindings, admission metadata and policy. It binds input/output meaning, acceptance/proof obligations, resource/effect limits and exact CC versions. M1 binds one work CC per subnode; additional work CCs use separate gated subnodes within their declared node. Verifier calls are separately governed checking assignments. The PRD permits broader capability sets, but arbitrary capsule member graphs and composite/merged CCs remain later work. Required invocation checks remain, and node-level aggregate verification authorizes successor nodes.

```mermaid
flowchart TB
    H[(Accepted hypothesis and protocol)]
    subgraph Task[Task: construct and measure the intervention]
        Build[POC builder CC] --> BD[Protected build checks]
        BD -->|valid| BV[Build verifier CC]
        BD -->|invalid| BG[Protected build gate]
        BV --> BG[Protected build gate]
        BG -->|Committed acceptance| Measure[Benchmark CC]
        BG -->|Blocked| Halt[Visible halt and retained evidence]
        Measure --> MD[Protected measurement checks]
        MD -->|valid| MV[Measurement verifier CC]
        MD -->|invalid| MG[Protected measurement gate]
        MV --> MG[Protected measurement gate]
    end
    H --> Build
    MG -->|Committed acceptance| Eval[Scientific evaluation CC]
    MG -->|Blocked| Halt
    Eval --> EV[Scientific-output Evaluator Gate]
    EV -->|Committed acceptance| Report[Delivery CC]
    EV -->|Blocked| Halt
    Report --> DV[Delivery Evaluator Gate]
    DV -->|Committed acceptance| O[(Released report and evidence)]
    DV -->|Blocked| Halt
    subgraph Legend[Legend]
        Key[Blue: CC work; purple: verification; amber: infrastructure; green: artifacts]
    end
    classDef work fill:#E8F0FE,stroke:#2563EB,color:#172554
    classDef verify fill:#F3E8FF,stroke:#7E22CE,color:#3B0764
    classDef control fill:#FEF3C7,stroke:#B45309,color:#451A03
    classDef data fill:#DCFCE7,stroke:#15803D,color:#052E16
    class Build,Measure,Eval,Report work
    class BV,MV,EV,DV verify
    class BD,MD,BG,MG,Halt control
    class H,O data
```

Build and measurement show their deterministic checks explicitly; combined scientific-output and Delivery Evaluator Gate boxes include deterministic checks, read-only assessment and protected decisions. Dependency arrows mean runner-mediated transfer of accepted artifacts, not direct calls that bypass gates. A verifier assessment comes from a separately governed verifier subnode; neither is the downstream work Node B. All participating invocation evidence is aggregated against the node contract. Only committed node acceptance releases successor nodes. Verifiers do not recursively require semantic verifiers.

## Scheduling and failure

Use the [failure and human-callback policy](failure-and-human.md) as the single routing authority. The [research port table](research-design.md#research-path-and-ports) supplies all stage inputs and outputs.

**Required now.** Dispatch dependency-ready nodes only after their required predecessor gates have durably advanced. Reuse an equivalent native topological scheduler. M1 uses one active research run and a sequential research path. Future independent-node execution requires declared effects/resources, an explicit execution profile and separate validation; it is not introduced by D1.

A blocking execution, verification, security, budget, or persistence failure stops new work dispatch for the whole run. Preserve in-flight outcomes and attempt evidence; cancellation does not undo effects already performed. Default to zero automatic repair or replay. A human correction creates attributable new work and must pass verification; a changed graph or objective needs a new plan and freeze. Never overwrite a failed attempt.

Browser disconnection does not cancel execution. Restart preserves accepted results and marks interrupted attempts paused for inspection. No native cache entry can replace an authoritative gate decision or justify repeating an uncertain effect. The first build starts a fresh run rather than resuming in place.

Scientific rejection or inconclusive measurement is different from infrastructure failure. Valid evidence and correctly applied criteria can advance to Delivery, which discloses the result and its limitations. All report preparation happens inside the application; the control plane transfers the accepted artifacts.


## Concrete execution boundary

The [core build scope](core-build.md) records the authorized promotion of fixed compilation plus protected planning into the core and the best-effort PRD deviations (D19).

Protected binding creates the enclosing node contract and exact [Subnode Execution Contract](reference/node-execution.md) before dispatch. Participating bindings name admitted declaration/body/dependency pins, role, effective authority and per-call limits; parent node limits bound their aggregate; subnode limits narrow each assignment. Inputs carry named typed ports and exact refs, outputs name catalog contracts/versions and evidence obligations. The guard profile is pinned in the contract; the bound check plan references that finalized contract without a hash cycle. Missing input or unsupported authority blocks dispatch, never becomes a placeholder observed artifact.
