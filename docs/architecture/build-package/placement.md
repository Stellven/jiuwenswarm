# Placement, evidence, and reuse

## Deployment and boundaries

**Required now.** Use one authorized local execution host with Python services, the existing TypeScript web UI, SQLite authoritative run state and filesystem artifacts. Product identity is user-scoped, distinct from the local OS account; durable account/profile state survives run/workspace deletion. M1 keeps one active authorized execution context, without enterprise multi-tenant administration. Keep internal modules distinct without making them separate services. One container may contain several native processes.

```mermaid
flowchart TB
    Browser[Browser]
    subgraph App[One application container]
        Web[Web assets and control plane]
        Planner[Optional Phase 3 planner CC]
        Binder[Protected contract and guard binder]
        Scheduler[Scheduler]
        Runner[CC runner and native harness]
        Verify[Verifier CCs: assessments]
        Gate[Protected gate host]
        Library[(CC library)]
        Bridge[Audited model bridge]
        State[Run-state module]
        POC[Restricted POC execution boundary]
        Web -->|Fixed preparation and static template| Binder
        Web -->|Bounded planning through runner| Planner
        Planner --> Binder
        Binder --> Verify --> Gate
        Gate -->|Validated and frozen plan| Scheduler
        Scheduler --> Runner
        Runner -->|Work result and evidence| Verify
        Gate -->|Committed release or halt| Scheduler
        Runner --> Bridge
        Runner --> POC
        Library -.-> Binder
        Library -.-> Runner
        Scheduler <--> State
        Verify --> State
        Gate --> State
        Web <--> State
        Profile[Account and profile adapter]
        Web <--> Profile
    end
    Browser <-->|Authenticated local endpoint| Web
    Bridge <-->|Provider request| Model[Configured model endpoint]
    Profile <--> Profiles[(Durable account and profile store)]
    Profiles -.->|Optional approved persistence adapter| Cloud[Cloud account or profile service]
    State <--> DB[(Mounted SQLite state)]
    Runner --> Files[(Mounted artifacts and raw evidence)]
    POC -->|Scoped workspace only| Workspace[(POC workspace)]
    subgraph Legend[Legend]
        Key[Blue: CC work; purple: verification; amber: infrastructure; green: data; gray: outside]
    end
    classDef work fill:#E8F0FE,stroke:#2563EB,color:#172554
    classDef verify fill:#F3E8FF,stroke:#7E22CE,color:#3B0764
    classDef control fill:#FEF3C7,stroke:#B45309,color:#451A03
    classDef data fill:#DCFCE7,stroke:#15803D,color:#052E16
    classDef outside fill:#F1F5F9,stroke:#475569,color:#0F172A
    class Planner work
    class Verify verify
    class Web,Binder,Scheduler,Runner,Bridge,State,POC,Gate control
    class Library,DB,Files,Workspace data
    class Browser,Model,Cloud outside
    class Profile control
    class Profiles data
```

The planner is invoked through the same runner; its separate box shows responsibility. The model bridge and restricted execution boundary are infrastructure, not CCs.

Build and serve the UI in the application image, starting from the existing repository `Dockerfile.claw` and `pyproject.toml`. Publish one host endpoint on loopback, retaining local session authentication. Listening on a container interface does not authorize LAN exposure. Persist data separately from the replaceable image; supply credentials through protected configuration, not declarations or output artifacts.

Use the existing Codex integration as the baseline model route. Preserve protected local IPC and owned execution context. Attempt approved alternate routing and verifier integration in isolated Delivery Phase 3 configurations, retaining the static Codex fallback. Every supported model call crosses the audited bridge; local run/capsule correlation stays in local telemetry rather than being added to provider prompts solely for attribution. Record time/calls and reliably available native spend/budget telemetry. Capture reliably exposed account allowance/limits/credits/reset separately; these are not per-invocation token or cost measurements. Absent reliable telemetry remains unavailable.

Generated POC code is untrusted. Docker packaging and a Python virtual environment do not prove confinement. Enforce scoped filesystem access, restricted identity, denied undeclared network/tools, resource limits, and separation from credentials, control state, library activation, and hidden fixtures. Do not expose the Docker socket. The owning task selects and verifies the available mechanism; if a mandatory boundary cannot be enforced, block execution. PRD §3.6.2 additionally forbids generated POC code from importing or using OS/network modules, including `os`, `sys`, `subprocess`, `requests`, `urllib` and `shutil`. The Builder/Verifier must reject a violating package before empirical execution; an intentional bypass is a required negative case. This product compliance rule does not constrain trusted provisioning/capture infrastructure in the same way. Prompt instructions or import scanning complement enforced confinement but cannot replace it.

Use a protected persistent account/profile store logically separate from run/workspace state; SQLite is a suitable initial realization, outside workspace deletion scope. Resolve account defaults then machine-local and project overrides into the frozen effective configuration. Never silently import prior unrelated research. A future cloud adapter may store approved profile/account fields; it cannot write gate state, access local project/hidden-fixture data, or become a remote control/callback transport. No cloud vendor is required for the local M1 baseline. Local workflow endpoints remain loopback with protected session authentication; stable account attribution does not replace these controls.

The [Compose client topology](automation.md#local-compose-topology) specifies network-port intent and benchmarker access. [M1 data ownership](m1-design.md#data-and-state-ownership) identifies each authoritative writer and consumer.

Verifier disclosure and read capabilities are deliberately smaller than work capabilities. The [review-context contract](guard-design.md#output-led-review-and-controlled-disclosure) specifies permitted evidence, model audience checks, immutable subject views, prohibited effects and non-advancing outcomes when necessary evidence cannot be disclosed. These are enforced boundaries, not prompt-only instructions.

## Data foundation

**Required now.** The run-state module owns durable lifecycle, frozen graph, attempts, decisions, and accepted artifact references. The scheduler and control plane use that authority. Native queues, journals, caches, and UI traces are projections or dispatch aids.

Store exact inputs, implementation/configuration identities, produced artifacts, runtime evidence, raw verifier assessments, and gate decisions with run/node/attempt correlation. Keep declared behavior distinct from observed behavior. Tool-call logs alone do not prove absence of hidden filesystem or network effects; an unobserved mandatory condition cannot be treated as passed.

Release-essential artifacts and decisions must commit before advancing. Storage failure blocks release. Optional diagnostics may fail without changing execution, but their absence is explicit. This reconciles the supplementary data-source's best-effort capture hooks with the master PRD's durable gate boundary.

Preserve raw evidence before workspace cleanup or native retention deletes it. Derived run records, conformance views, scorecards, and exports can be rebuilt from that evidence. Separate agent working context from authoritative records. Keep credentials out of capture; raw prompts and supplied data remain locally protected. Any export must respect its permitted audience and hidden-fixture boundary.

Scientific benchmarking executes the user's baseline/treatment protocol. Platform benchmarking compares system variants on matched inputs and frozen effective configurations. Both use the same attribution foundation, but their measurements and conclusions are distinct. Exports record what actually ran, seeds where supported, component versions, gate evidence, and unavailable measurements. Gate-disabled ablations are evaluation runs, not valid product runs or admission evidence.

## Offline RSI

The [human-callback policy](failure-and-human.md#offline-rsi-is-a-separate-callback-policy) distinguishes ordinary candidate feedback, session faults and explicit activation. Runtime Verifier (Evaluator Gate), offline referee and fixture oracle are different roles, defined in [the glossary](glossary.md).

**Required now for full M1; outside the first build.** Prepare the independent interface early so offline work need not wait for planner implementation. The initial required target is the pure `rank_opportunities` helper inside the Screening CC. Keep its input/output meaning, required dimensions, Top-1 behavior, and effect boundary fixed. Candidate mutations operate on a sandbox copy; production remains unchanged.

```mermaid
flowchart TB
    Library[(Admitted parent version)] --> Copy[Eligible target copy and visible development fixtures]
    Copy --> Proposer[Fixed offline improver]
    Proposer --> Candidate[Inactive candidate and lineage]
    Candidate --> Referee[Protected independent referee]
    Hidden[(Hidden loop and final fixtures)] --> Referee
    Referee --> Evidence[(Bounded results and audit evidence)]
    Evidence --> Proposer
    Candidate --> Admission[Admission and compatibility checks]
    Evidence --> Admission
    Admission --> Human[Human activation or refusal]
    Human --> Library
    subgraph Legend[Legend]
        Key[Blue: improvement work; purple: verification; amber: infrastructure; green: data]
    end
    classDef work fill:#E8F0FE,stroke:#2563EB,color:#172554
    classDef verify fill:#F3E8FF,stroke:#7E22CE,color:#3B0764
    classDef control fill:#FEF3C7,stroke:#B45309,color:#451A03
    classDef data fill:#DCFCE7,stroke:#15803D,color:#052E16
    class Proposer,Candidate work
    class Referee verify
    class Copy,Admission,Human control
    class Library,Hidden,Evidence data
```

The [RSI connection design](offline-rsi.md) defines target profiles, data partitions, replay and future improver seams. Target 1 remains a sandbox child/evidence deliverable; the activation arrow applies only to explicitly eligible adoption, not automatic Target 1 production change.

The feedback arrow returns only the approved bounded loop information. Hidden fixture content, expected outputs, per-case hidden results, and final-evaluation feedback remain outside the proposer and candidate. Separate development, hidden-loop, hidden-final, and milestone data. Reserve final evaluation for terminal assessment; freeze scoring and evaluation identities before the session. Compare parent and child under the same relevant configuration and enforce the declared query/resource limits.

RSI may change only explicitly eligible implementation parts. It cannot change contracts, gate/verifier/check assets, security or mutation permissions, evidence stores, fixture custody, model weights, or activation controls. Enforce restrictions outside the mutable target. Preserve attempts, lineage, scoring, and violation evidence. Admission and human activation are separate from a better score; retain rollback. Target 2 mutates explicitly permitted Screening implementation text only when bounded headless model execution is available (PRD 4.4.1); otherwise defer it to M2 without blocking required Target 1 or M1 completion.

## Native reuse

**Required now.** Start from native UI/transport, SwarmFlow scheduling, Symphony agent/harness components, existing model integration, storage, and diagnostics. Historical integration audits are source leads, not proven integrations or current policy. [Human callback](failure-and-human.md#pattern-and-reuse-evidence) records current inspected native interaction leads.

At the installed dependency version, verify adapter behavior for swallowed exceptions, hidden retries, journal/cache replay, duplicate effects, cancellation, and background lifecycle. In particular, a native cached result cannot establish a committed CC gate pass. Keep model-process ownership separate from unrelated interactive chats. Add only missing adapters and capsule/runtime behavior; Spec Kit chooses files and APIs.
