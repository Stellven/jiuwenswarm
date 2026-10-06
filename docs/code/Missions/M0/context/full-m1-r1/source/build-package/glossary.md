# Vocabulary and PRD translation

Use this page when moving between the PRD, architecture, owner contributions, and coding tasks. Different names do not imply different systems. The [coverage map](coverage.md) identifies actual changes; translations alone never amend product scope.

## Components and responsibilities

| PRD or owner wording | Architecture wording | Meaning and reading destination |
|---|---|---|
| Ingestion; Qualified Intake Package (§3.1) | Intake; qualified intake | Capture original text, extract permitted documents, and bind separately supplied assets to a run. [M1 workflow](m1-design.md). |
| Requirement Compilation / Intention Compiler (§3.2, §4.7) | Intent compiler followed by Requirement compiler | Two independently checked responsibilities under D5. Accepted intent is intermediate; accepted Research Brief is the downstream contract. [TRIAL-1](immediate-plan.md), then [workflow](workflow.md). |
| Research Brief / `Research_Brief.json` | Research Brief | Same accepted objective, scope, constraints, preferences, metrics, and evidence obligations. File spelling is the PRD artifact name, not a second contract. |
| Default DAG; TaskGraph; Swarmflow (§4.6, §4.8) | Frozen graph; scheduler; harness | Graph is a plan, scheduler determines readiness, harness supervises execution. Phase 1 uses a fixed operational fallback. D1 supplies bounded direct CC selection for Phase 3, preserving the same research obligations and protected execution boundary. [Workflow](workflow.md). |
| Capability Capsule; `search_capsule.md`, etc. (§4.1) | CC declaration and implementation | A prompt file is one implementation form; it does not replace typed ports, immutable implementation identity, or checks. [Capsules](capsules.md), [declaration](capsule/declaration.md). |
| CC Runner (§4.6, §4.9) | Runner | Shared execution infrastructure for work and verifier CCs. Builder is a work responsibility, not another universal runner. |
| Builder / POC Implementation (§3.6, §4.9) | POC builder CC | Constructs bounded code, harness, dependency declaration, and package; analytical outputs belong to their own CCs. |
| Verification; verifier | Structural and semantic checking | Checks outputs against the active contract, accepted inputs and required execution evidence; produces structured findings/verdict with reasons and evidence references. Verification can conceptually operate without controlling advancement. [Exact boundary](capsules.md#exact-verification-boundary). |
| Gating | Advancement-policy application | Applies workflow advancement policy to the verification verdict. Protected host code aggregates and durably records the final verdict before releasing or blocking downstream work. |
| Evaluator Gate (§4.2); verifier gate; gate capsule | M1 integrated verification and gating | Tier 1 deterministic checks → Tier 2 verifier assessment → protected host verdict and durable advancement-policy application. “Verifier = Evaluator Gate” names this M1 composition, not general equivalence. “Gate capsule” means the assessment CC only; never a capsule with independent release authority. [Exact boundary](capsules.md#exact-verification-boundary). |
| AI Reviewer Agent (§4.3.4); infrastructure `verifier_capsule.md` | Runtime verifier CC | Read-only semantic assessment executed in a separate context, supplied through the model bridge. Its role/profile names the question; it is not a separate service for every stage. |
| Mandatory deterministic guard / guard profile / binder | Reusable admitted check or trusted host primitive / independently approved obligation-to-check recipe / protected assignment into a frozen contract. [Guard design](guard-design.md). A planner proposes extra checks but cannot approve its own mandatory profile. |
| Scientific evaluator (§3.8); `scientific_evaluator_capsule.md` | Scientific evaluation CC | Interprets admitted measurements against the frozen protocol. Its scientific verdict is data subsequently checked by a runtime verifier. It cannot release itself. |
| Secure Fixture Oracle; independent evaluator/referee (RSI owner §3.Y; master §4.4) | RSI referee and fixture oracle | Protected offline evaluation. Oracle controls hidden fixture access; referee runs fixed scoring and returns only permitted feedback. A runtime verifier is not given hidden fixtures. [Offline RSI](placement.md#offline-rsi). |
| Certification / registry / standing | Admission / library / eligibility | Admission records whether a version is eligible; activation selects an admitted default; suspension revokes eligibility. A scorecard is evidence, not activation authority. |
| Data Foundations / System Memory (§4.5) | Run-state authority plus evidence and derived records | SQLite owns release/lifecycle; files retain raw evidence and exports. Native Task Memory and Coding Memory are reasoning aids. D6/D9 reconcile supplementary capture defaults. [Data design](m1-design.md#data-and-state-ownership). |
| Stage Evidence Bundle | Captured subject and execution evidence | Exact output plus inputs, runtime observations, check context, and attributable references used by the verification boundary. |
| Capsule Run Record; Run Bundle; scorecard | Derived per-invocation record; complete run evidence; version summary | Preserve PRD export meanings. Verifier calls are attributable too; a scorecard cannot erase failed attempts or certify unmeasured reliability. |
| Scientific Benchmarking (§3.7) | Scientific benchmark CC | Baseline then treatment under the user's frozen protocol, inside the research run. |
| Phased System Validation; external benchmark harness | Platform benchmarker | Ordinary headless client comparing platform configurations on matched cases. It does not construct the user's scientific verdict. [Automation](automation.md). |

## Identities, ports, and outcomes

**Use role-qualified names.** Write “intent verifier CC”, “plan verifier CC”, “RSI referee”, “fixture oracle”, or “protected gate host”. Avoid bare “verifier agent” where two paths are possible. A shared verifier implementation may have multiple pinned profiles; profile isolation and evidence scope remain explicit.

| Term | Rule |
|---|---|
| TRIAL-1 / TRIAL-1 | TRIAL-1 names the intent pair and reserves a distinct future coding TASK. Main M1-001 remains the Codex adapter. The conflicting former local M1-001 trial identity and branch-local trial location are retired; register colocated native files in docs/code/Missions/M1/TRIAL-1/ before specification. |
| Stage / task / node / attempt | Delivery Phase names baseline/RSI/dynamic integration. Implementation Stage names integration milestones 0–8. A research responsibility is a workflow role; task groups objectives; node is an objective instance with a Node Execution Contract; attempt is an execution of that node; invocation identifies each subordinate CC call. A coding TASK and native SwarmFlow runtime phase are separate identities. |
| Declaration name / version / hash | Stable capability name, display version, and exact immutable identity are distinct. Never use a display label as a content pin. |
| Node Execution Contract (§4.1.3–4) | Protected run-specific objective, accepted port bindings, output/check/evidence obligations, exact participating CC pins and effective limits; it may narrow admission but never widen it. [Shapes](contracts-and-native-reuse.md). |
| Product account / local execution identity | Stable product user and durable profile are independent of OS identity/workspace. Local token/OS restrictions authorize the execution host; cloud profile persistence does not authorize remote workflow execution. |
| Artifact type / port / reference | Type names semantic meaning; port names the input/output role; reference identifies stored content. A filesystem path alone does not prove accepted identity or freshness. |
| Freeze / protocol registration | Graph freeze fixes topology and bindings before research execution. Hypothesis registration later fixes experimental criteria before build/measurement. Future output references are not fabricated values. |
| `PASS_WITH_KNOWN_LIMITATIONS` | Advances only if every mandatory condition passed; carry warnings forward. It cannot excuse a failed required boundary. |
| `ENVIRONMENT_BLOCKED` / `BLOCKED` | Detailed runtime verdict / normalized test or display status. Preserve the detailed value and reason. `ESCALATE_TO_HUMAN` is an action, not a sixth gate verdict. |
| Scientific `FAIL` or `INCONCLUSIVE` | Hypothesis rejected or evidence between pre-registered bounds. Validly executed scientific evaluation can still receive infrastructure `PASS` and reach Delivery. |
| NOT_RUN / unavailable / stale | No observation, unavailable telemetry, or invalidated evidence. None means zero cost, failed science, or a pass. |

## Naming and schema principles

Use descriptive capability names consistently across declarations, diagrams, task agreements, and records. Existing PRD artifact names remain the translation anchors. Spec Kit owns exact identifier syntax, wire keys, enum serialization, and file layout through versioned agreements; examples in this design do not introduce competing schemas.

Every shared payload has one semantic owner, a version, validation rules, and identified producers/consumers. Distinguish missing, unknown, unavailable, and not applicable. Preserve units, metric direction, evidence origin, warnings, and scope. Content and identity are immutable after acceptance; derived summaries cite their source. Additive fields require explicit compatibility rules rather than assuming all readers tolerate them. Reject unsupported mandatory semantics; do not silently drop them.

Keep reusable capability declaration, Node Execution Contract, invocation binding, runtime observation, verifier assessment, authoritative gate decision, and aggregate score separate. A schema-valid self-assertion is not evidence of execution. Future readers must be able to reconstruct which versions, policy, inputs, and accepted predecessors produced a decision.
