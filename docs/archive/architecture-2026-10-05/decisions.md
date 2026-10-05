---
id: arch.decisions
type: ledger
level: present
status: draft
version: 3
provides: [arch.decisions, arch.deviations, arch.open]
consumes: [arch.terms]
depends_on: [terms.md, flow.md, placement.md, verification.md, runtime.md, rsi.md, prd-map.md]
tags: [decisions, deviations, open-items, start-here]
prd: [1.6, 2.7, 3.2, 3.2.1, 4.1.2, 4.4.5, 4.7, 4.8.2]
---

# Decisions, PRD deviations and open items

PRD: 1.6, 2.7, 3.2, 3.2.1, 4.1.2, 4.4.5, 4.7, 4.8.2

> Answers: What have we decided, where do we deviate from the PRD, and what is still open?

Only current decisions are here. Superseded ones live in git history. Each row says why we chose it and where the detail is. Evidence status for every row is **specified**; none is implementation-validated.

## Current decisions

| ID | Decision | Why | Details |
|---|---|---|---|
| A1 | [Fixed outer flow](flow.md#term-fixed-outer-flow) in [SwarmFlow](system/integration.md#term-swarmflow): intake, intent CC + [Gate](verification.md#term-gate), requirement CC + Gate, planner, validate/bind/freeze, dispatch, delivery. Planned [nodes](system/nodes.md#term-node) are fixed after freeze. | The PRD wants a predictable flow. Fixed positions keep it testable. Task nodes give flexibility for what is done inside it. | [flow](flow.md) |
| A2 | The planner is an ordinary service, not a CC. In M1 it emits one fixed template DAG through the full [validator](system/planner.md#term-plan-validator). Model-proposed DAGs exist only in the isolated experiment track. | Planning is orchestration, not reusable capability. Putting it behind a validator keeps a bad plan from running. | [planner](system/planner.md) |
| A3 | Intent is two CCs: `research.compile_intent` (model-backed: compile, validate, nested fidelity review, bounded repair) and the shared verifier with profile `research.accept_intent.v1`, which is also the Gate `G_intent`. Converted from the AI4Research intent compiler. | Intent drift is the costliest error: every later step builds on it. A model compile with an independent verifier and bounded repair catches meaning errors that rules cannot. | [intent compile](capabilities/intent-compile.md), [intent gate](capabilities/intent-gate.md) |
| A4 | Capsule count is an outcome of [boundaries](system/modules.md#term-boundary), not a target. Inventory is derived from the capability pages. The final inventory is 13 CC identities. | Boundaries change as we learn. A fixed target would force wrong splits. | [capabilities](capabilities/README.md) |
| A5 | Delivery is a module, not a [capsule](capsule/capsule.md#term-capability-capsule), and has no Gate. `research.write_report` is a capability with its own page. | Delivery is deterministic assembly. Making it a capsule would add admission and [RSI](rsi.md#term-rsi) surface for no benefit. | [terms](terms.md), [write report](capabilities/write-report.md) |
| A6 | The verifier is a CC (`research.verifier`), one identity, reused at every Gate through pinned profiles. | One verifier is easier to trust and compare than many. Profiles give per-stage criteria without new identities. | [verification](verification.md) |
| A7 | Every dispatch call has a Gate. Tests are derived from the producer's [Declaration](capsule/fields.md#term-declaration). Gate profiles `research.accept_*` cover Hypothesis through Report; the [delivery manifest](capabilities/delivery.md#term-publication-manifest) check belongs to delivery. | Checking right after each call stops errors from spreading. Declaration-derived tests mean writing a good Declaration gives a test for free. | [verification](verification.md) |
| A8 | A failed Gate [halts](system/lifecycle.md#term-halt) the whole run, including sibling branches. Zero autonomous retries. | Continuing after a failure hides faults and corrupts evidence. A clean halt keeps results trustworthy. | [runtime](runtime.md) |
| A9 | [Verification](schemas/verification-record.md#term-verification), then release, are committed before any successor dispatch. Supervisor is the only writer. | If a pass is not durably saved, a crash could release work on a decision nobody can find. | [lifecycle](system/lifecycle.md) |
| A10 | Gate-role CCs have zero RSI-mutable components, so success rates compare against a fixed referee. | If the referee changes, a capsule success rate means nothing. | [verification](verification.md) |
| A11 | Scientific verdict and infrastructure verdict are separate. A valid negative result reaches the report. | A rejected hypothesis is a valid result, not a system fault. They need separate answers. | [evaluation](capabilities/evaluation.md) |
| A12 | One Docker container, modular monolith. Inner restricted processes for generated code, [operators](capabilities/README.md#term-operator) and [fixtures](system/test-surfaces.md#term-fixture). | One image is simple to ship and test. Inner restricted processes keep generated code and credentials apart. | [placement](placement.md) |
| A13 | [Model routing](model-routing/README.md#term-model-routing) sits inside a model call and never selects capsules. Production route is static Codex through a [bridge](system/model-bridge.md#term-model-bridge). | The plan decides what [runs](system/lifecycle.md#term-run); routing only decides which model serves one call. Mixing them makes runs unreproducible. | [model routing](model-routing/README.md) |
| A14 | Codex login lives on its own persistent volume used only by the bridge, with its own login separate from any desktop Codex profile. Same single container. | Copying logins per run lets two writers corrupt a session. One persistent volume has one writer. | [model auth](system/model-auth.md) |
| A15 | Field tables are the single source of [payload types](types/types.md#term-payload-type) and generate JSON Schema. Core types are closed; changes make a new version. | One table per type means a type, its schema and its example cannot drift. | [types](types/types.md) |
| A16 | `obs_id` joins everything inside a capsule call. Telemetry and [Data Foundation](system/storage.md#term-data-foundation) records are [derived views](system/storage.md#term-derived-view). | One join key lets any view be rebuilt from the records. | [observability](system/observability.md) |
| A17 | RSI is offline, targets only eligible capsules, uses a [private oracle](capsule/fixture-oracle.md#term-fixture-oracle) and needs human activation. | Offline keeps live runs stable. A private oracle keeps the improver from gaming its tests. | [rsi](rsi.md) |
| A18 | [Puppet admission](capsule/admission.md#term-puppet-admission) lets a developer allowlist exact hashes as `exempt`. It invents no test results and cannot release a node. | Developers need a way to admit a known capsule without a test campaign, but it must not look like a tested one. | [admission](capsule/admission.md) |
| A19 | Version, assurance and activation are separate. Activation changes future snapshots only. | Separating them lets a version be admitted without going live, and rolled back without losing history. | [library](capsule/library.md) |
| A20 | Build in thin slices: one capsule, then one connected capsule, proving each seam. | A defect is easy to find when only one new piece was added. | [build order](build-order.md) |
| A21 | SkillFuzz-style analysis of capsule-set interactions is deferred. Current [checks](capsule/fields.md#term-check) prove interface compatibility, not semantic safety of every combination. | Not needed to build and test the core. Cost is high. | [library](capsule/library.md#deferred-capsule-interaction-analysis) |
| A23 | No automatic librarian in M1. Standing changes (suspend, deprecate, roll back, activate) are manual. `certified` assurance is not granted in M1. | Background automation changes behavior nobody asked for. Manual standing changes are traceable. | [library](capsule/library.md) |
| A24 | Delivery is ordinary code with a deterministic manifest check and no Gate. Every dispatch call has a Gate. A nested operator call (`op.*`) gets a mechanical Verification persisted before it returns and is covered by the parent node's Gate. The nested verifier review inside `research.compile_intent` is validated by the calling capsule and is not itself Gated. | Delivery only assembles accepted results. Nested calls sit inside a node, so the node's Gate covers them. | [delivery](capabilities/delivery.md), [verification](verification.md) |
| A25 | Gate API is `gate(obs_ref) -> GateResult`. `CcBackend` on the supervisor side calls the [Gate host](capsule/gate-host.md#term-gate-host) after the supervisor commits the [Observation](schemas/observation.md#term-observation): commit, then Gate, then release. Gate host and Gate front-end (`CcBackend`) run in the supervisor process. | One call shape means one place to test and one place to fault-inject. | [Gate host](capsule/gate-host.md) |
| A26 | A run pins one [library snapshot](capsule/library.md#term-library-snapshot) at launch and has two freeze points. Launch: freeze the snapshot and the [prep plan](types/run-plan.md#term-prep-plan) (intent step, requirement step) with their Gates. After the requirement Gate releases: the planner emits the DAG, the validator checks it, the binder [freezes](system/lifecycle.md#term-freeze) it (phase `planned`), all from the same snapshot. Accepted requirements are immutable once [released](system/lifecycle.md#term-release). Task nodes read prep outputs as `prep.<step_id>.<port>`. | The DAG depends on accepted requirements, so it cannot exist at launch. One snapshot and two freezes keep every run consistent and reproducible. | [lifecycle](system/lifecycle.md), [planner](system/planner.md), [run plan](types/run-plan.md) |
| A27 | Every message, record and API envelope between modules has a JSON Schema in `contracts/`, with fixtures and an index. Docs describing communication link the def. | Coding agents generate types from schemas. Prose alone leads to different guesses. | [contracts](contracts/README.md) |
| A28 | Capsules are run by the [CC runner](capsule/runner.md#term-runner), never by native agents. A capsule gets no ambient workspace: only snapshots and one attempt directory through brokers. Confinement reuses [jiuwenbox](isolation.md#term-jiuwenbox) (Bubblewrap, [Landlock](isolation.md#term-landlock), [seccomp](isolation.md#term-seccomp), netns) with hard requirements; native permissions are not counted as isolation. | Native agents have ordinary file and shell tools in one OS user with permissions off by default. We need per-call limits we can prove. | [isolation](isolation.md) |
| A29 | Codex is a text-only model endpoint in M1 production. Codex agents with tools are a separate `agent` [kind](capsule/capsule.md#term-capsule-kind), proposed for later: same confinement, attempt directory only, no network, no login, hard budgets, Gate on produced files. | Tool-using agents widen what can go wrong. They need the same proofs as generated code before they are allowed in a run. | [isolation](isolation.md#codex-agents-inside-a-capsule) |
| A30 | Reuse native features when they do the job and keep our invariants. Reuse the Swarmflow engine (`cap`, `budget`, `abort_event`), the jiuwenbox HTTP API for per-attempt sandboxes, and the doctor as check zero. Wrap the journal (cache only), human session and run view. Build store, skill and tool runners, config freeze, planner, Gate and workspaces. | Native pieces are cheaper and known, but several defaults break single writer, zero retries or Gate-before-release. | [reuse](reuse.md) |
| A31 | A halt is a `BaseException` and also sets the engine's `abort_event`. The launcher always passes `CcBackend` and `run_id`, and passes only references as args. `CcBackend` never raises, so engine retries have nothing to retry. | Native `parallel()` swallows ordinary exceptions, and the engine falls back to a mock backend. Either would let work continue after a failed Gate. | [reuse](reuse.md), [integration](system/integration.md) |
| A32 | The supervisor is the only store writer. The runner returns its Observation, [Artifacts](schemas/artifact.md#term-artifact) and capture and the supervisor commits them on its behalf (`commit_request` and `commit_result`, boundary BD21). `runner_response` complete means the supervisor committed the Observation. `record_input` is a supervisor-side control function, not a runner operation. | One writer keeps durable order simple and testable. | [runtime](runtime.md), [lifecycle](system/lifecycle.md) |
| A33 | A gate, nested or admission call carries no `caller` in `runner_request`. Caller kind, parent observation and ordinal come from the [dispatch reservation](system/records.md#term-reservation) named by `reservation_ref`. The supervisor calls the validator and the binder. The oracle writes only its private namespace through its own writer. | A caller cannot claim a kind it does not have. | [runner](capsule/runner.md) |
| A34 | Every local socket and child channel uses length-prefixed frames (4-byte big-endian length, then UTF-8 JSON), at most `cc.ipc.max_frame_bytes` (default 1 MiB). Large values go by reference. | One framing is easy to fuzz and bounds memory. | [runtime](runtime.md) |
| A35 | Exit codes: 0 success, 2 launch or configuration rejected, 3 halted, 4 environment unavailable. Benchmark clients use the HTTP API (`benchmark_request`, `export_request`), not `launch_request`; HTTP status codes are separate from CLI exit codes. | CI and clients need stable codes. | [workstation](system/workstation.md) |
| A36 | The M1 planner makes zero model calls and writes no planning reservation. The planner-to-bridge edge, planning scope, planning reservation and model-proposed DAGs exist only in the isolated experiment track. | A fixed template needs no model. | [planner](system/planner.md), [experiments](system/experiments.md) |
| A37 | There is exactly one requirement call (`research.compile_brief`), one model pass. Intent is a bounded loop: compile, validate, nested review, repair. Policy key `intent.max_repairs` (default 1, hard cap 4) is in [policy](schemas/policy.md). Only tuning after fixtures is open. | Intent drift is costly, so repair is bounded. Requirements build on accepted intent. | [intent compile](capabilities/intent-compile.md) |
| A38 | RSI: `research.compile_intent` is eligible (code and its two prompts, model-backed, paired repeated calls), a third target mode beside the helper and the Screening prompt and rubric text. The AI4Research prompts are visible development fixtures. Admission provider is chosen by policy: `tested_admission` (provisional) is the default, Puppet is available by developer allowlist (exempt). Either way the child is admitted inactive. | Intent quality is the lever with the most effect. Policy keeps provider choice out of code. | [rsi](rsi.md), [admission](capsule/admission.md) |
| A39 | The model bridge has its own page: a Unix socket, a capability token in the first frame, length-prefixed frames, one blocking exchange per [turn](system/model-bridge.md#term-model-turn). A `status` operation is the only use of queued and running states. | A small fixed protocol is testable. | [model bridge](system/model-bridge.md) |
| A40 | The image contains the jiuwenbox HTTP server, its token and policy, and the doctor [probes](system/environment.md#term-probe) it. `op.scholarly_search` declares egress, but the child has no network and the egress is brokered. | One image stays shippable. Brokered egress keeps default-deny network. | [isolation](isolation.md), [placement](placement.md) |
| A41 | A crash or kill never resumes by itself. On restart the supervisor writes a halt report with reason INTERRUPTED and waits. `cc resume <run_id>` by a human creates the `human_review_record` (action `resume_after_fix`) and a new attempt of the interrupted step under unchanged pins. Test-only seam: config key `cc.test.review_injection`, refused by the production profile. | A hidden resume could repeat a paid or side-effecting call. | [lifecycle](system/lifecycle.md) |
| A42 | `AUTH_RELOGIN_REQUIRED` and model unavailable halt the run as ENVIRONMENT_BLOCKED. After login a human `resume` starts a new attempt of that step under the same pins. The possibly-paid turn is never resubmitted without that command. | Money and evidence both need a human decision. | [model auth](system/model-auth.md) |
| A43 | A declared failure mode (for example `NO_ELIGIBLE_OPPORTUNITY`): the capsule ends the call with outcome error and its declared failure code. The Gate host maps it to INCONCLUSIVE with HALT and ESCALATE_TO_HUMAN. It is not FAIL, not a capsule fault and not a scientific negative result. | The failure is expected, so it needs review, not an alarm. | [verification](verification.md) |
| A44 | Rollback is an `activation_request` pointing at a historical admitted hash. `standing_change_request` covers only suspend, deprecate, retire, revoke and restore. First activation: `cc bootstrap` (the installer) admits and activates the seed capsules with `expected_current_hash` null, actor `installer`. Toy capsules are bootstrapped at build step 1 and research capsules when each is ported. | One path for moving the alias. | [library](capsule/library.md) |
| A45 | US-18 (Codex agent with tools) is Future, not M1 acceptance; [isolation](isolation.md) keeps the design. The benchmark export schema is `PENDING_SOURCE`, so US-16 is partial by design. | Not needed for M1 acceptance. | [stories](stories.md) |
| A46 | Build order: doctor core at step 0 and restricted-child probes at step 2; confinement adapter, capture collector and event bus at step 2; installer and auth provider at step 0; intake is `cc/intake.py` with a toy intake at step 4; D6 is the step 10 exit and the benchmark API follows it. B15 admission validation is at step 1 with test calls wired at [steps](system/nodes.md#term-step) 2 and 3. The launcher needs a toy plan at step 4 and the validator only from step 7. RSI needs the capture and export [blocks](system/modules.md#term-block). | Each step then has what it needs. | [build order](build-order.md) |
| A47 | Proposed commands: `cc attempts clean <run> <step>`, `cc library list`, `cc library standing <name>`, `cc verdict show <decl_hash>`, `cc status`, `cc inspect`, `cc artifacts`. | A human needs a way to inspect and recover. | [tools](capsule/tools.md) |
| A48 | Pages use no people or team names and no ownership wording. Module-spec pages are done when their [V rows](system/test-surfaces.md#term-v-row) pass. Present pages use tables of at most 5 columns; wide reference matrices are allowed on detail pages. Data Foundation sources are verbatim. | Short, uniform pages are easier to check. | [standards](standards.md) |

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-deviation"></a>**Deviation** (also: deviations, PRD deviation) | A place where the design deliberately differs from the PRD, listed with what the PRD says, what we do and what is still respected. |
| <a id="term-pending-source"></a>**PENDING_SOURCE** | An input we need from the PRD, the coding side or an external team and do not have. It is never guessed and is listed under Open. |
| <a id="term-pending-design"></a>**PENDING_DESIGN** | A design choice we have not made yet. It is listed under Open. |
| <a id="term-stale"></a>**STALE** | A check result recorded against an older revision of the thing it checks. It is never a pass. |
| <a id="term-not-run"></a>**NOT_RUN** | A check that was never run. It is never a pass. |
| <a id="term-blocked"></a>**BLOCKED** | A check that could not run, for example because a service is missing. It is never a pass. |

## PRD deviations

The PRD is `docs/product/prd-m1-full-2026-10-02.txt`. These were chosen to build the system as defined. Everything the PRD blacklists stays out unless listed. Map of clauses to design: [prd-map](prd-map.md).

| # | PRD says | We do | Still respected |
|---|---|---|---|
| 1 | Phase 1 DAG is hardcoded; planner bypassed (2.7, 4.8) | A planner service emits the DAG once from accepted requirements; it is validated, bound and frozen before any dispatch. M1 emits one fixed template with no model call. | no live restructuring, no replanning after failure, no parallel swarms |
| 2 | Dynamic intent compilation is Phase 2; Phase 1 is one fixed one-shot compiler (3.2, 4.7) | An intent CC derives intent first (bounded loop for intent), then one requirement call (one pass for requirements). Existing compiler as base, no dialogue. | no interactive clarification, no dynamic workflow selection |
| 3 | Evaluator Gate between governed stages (4.2) | Gate after every capsule call, built from the Declaration; verifier is itself a CC with zero RSI mutability | two-tier gate, read-only verifier, frozen referee |
| 4 | Native process sandbox, containers deferred (4.1.4, 5.4.3) | One Docker container plus inner restricted processes | no per-task containers, no Docker socket, no cluster |
| 5 | Human activation of RSI versions (4.4) | Adds a developer-controlled Puppet admission for exact hashes (`exempt`) | RSI children stay inactive until a human activates |
| 6 | Intent and requirement compilation are one single-turn LLM pass (3.2.1, 4.7) | The intent CC makes model calls in a bounded loop: compile, deterministic validate, independent fidelity review (nested verifier call), repair (default 1, hard cap 4). The requirement CC keeps one model pass. | no user dialogue, no dynamic workflow selection |
| 7 | One [Brief](types/research-brief.md#term-research-brief) from one compiler (3.2) | The prep plan has one requirement call. A second one needs a new decision. | single Brief to the planner |
| 8 | Strict admission with self-tests, one `provisional` level (4.1.2) | Two admission providers: tested (`provisional`) and Puppet (`exempt`) | no `certified`, no automatic librarian |
| 9 | RSI targets only Screening (4.4) | `research.compile_intent` code and prompts are also RSI-eligible. Gate CCs stay excluded. | same referee, oracle and human activation |

Deviations 1-9 are accepted. The coding task register records them as given.

## Open

Items architecture cannot settle alone. Each blocks only the work it names.

### Pending source (do not invent)

| Item | Affects | Note |
|---|---|---|
| Benchmark export schema | step 10, US-16 | `PENDING_SOURCE`: the harness side supplies it. US-16 is partial by design. |
| Alternate-endpoint access approval (alternate verifier model, router) | isolated track | mocks until approved |
| [GateProfile](schemas/profiles.md#term-gateprofile) id convention and profile hash rule | steps 3-6, verifier | [verification](verification.md) |
| Declaration-derived Gate builder: API and test-record shape | step 3, freeze | authority and placement are decided; shapes are not |
| Toy fixtures for steps 1-7: one pure capsule folder, a two-node toy plan, a toy Gate profile, a type-agnostic delivery contract and what "answer out" is for a toy | steps 1-7 | [build order](build-order.md) |
| Fake model bridge replay file format for system tests; whether a toy node may use a deterministic-only Gate profile | steps 3-7 | [test surfaces](system/test-surfaces.md) |
| First-epoch policy example with the runner and check numbers; minimal config keys per build step | steps 0-3 | [environment](system/environment.md) |
| Store fault-injection seam | steps 3-4 | [storage](system/storage.md) |
| Model bridge capability token: the first-frame token has no schema def yet | step 0, bridge | [model bridge](system/model-bridge.md) |
| **Naming scheme:** consolidate every name (capsules, steps, nodes, types, records, files, code paths) with the PRD and the coding side | all pages, schemas, code paths | names here are working names; expect renames |
| Experimental compiler requirement output type; generalist settings (future) | isolated track | [experiments](system/experiments.md) |

### Validation not yet run

| Item | Acceptance evidence |
|---|---|
| Nested user-namespace and seccomp profile for generated code on Linux Docker Engine and macOS Docker Desktop | doctor probes pass; otherwise `UNSUPPORTED_SECURITY_PROFILE` and blocked |
| RSI adversarial suite (24 cases RSI-S01 to RSI-S24, repeated; [attacks](capsule/rsi-attacks.md)) | all blocked, logged, reconcilable |
| Native workflow spans for CC calls with no native multi-agent worker | one run showing the join to CC records |
| Native web run view renders a run with no multi-agent session | first integrated run |
| Existing intent compiler conforms to the intent type | component invocation |
| Hash-pinned offline wheelhouse per supported platform | clean offline install |
| Effect enforcement per backend (`denied`, `mediated`, `observed`, `unsupported`) | enforcement matrix with injected violations |
| Each measurement method has an adapter, coverage and fixture | Fixture evidence; missing blocks only that experiment |

## Borrowed patterns

Pattern names used across pages. Each is a design pattern, not proof of correctness here.

| Pattern | Source | Used for |
|---|---|---|
| Small immutable decisions | [Architecture Decision Records](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) | this ledger |
| Typed reusable components | [Kubeflow component spec](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/) | capsules, [port types](schemas/port-types.md#term-port-type) |
| Versioned schemas, explicit migration | [Confluent data contracts](https://docs.confluent.io/platform/current/schema-registry/fundamentals/data-contracts.html) | types |
| Immutable versions, movable alias | [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/) | library, activation |
| Policy separated from data | [Open Policy Agent](https://www.openpolicyagent.org/docs) | Gate profiles |
| Persist progress before release | [Temporal workflow execution](https://docs.temporal.io/workflow-execution) | lifecycle |
| Consumer and provider verify one contract | [Pact](https://docs.pact.io/) | seam checks |
| Linked trace identity | [OpenTelemetry traces](https://opentelemetry.io/docs/specs/otel/trace/api/) | `obs_id` |
| Unprivileged namespace isolation | [Bubblewrap](https://github.com/containers/bubblewrap/blob/main/README.md) | generated-code child |
| Spec vs status, controller reconcile loop, admission, immutable digests with movable tags, securityContext, default-deny network, probes, ambassador sidecar | [Kubernetes](https://kubernetes.io/docs/concepts/) | [k8s-lens](k8s-lens.md) |
| Hash-pinned offline installs | [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/) | POC dependencies |

## Change log

| Date | Change |
|---|---|
| 2026-10-05 | Library reorganized: present pages, capabilities, capsule, system, contracts. Old archive, reviews, presentation and stories removed |
| 2026-10-05 | Intent redesigned as two CCs (compile with bounded review and repair, plus verifier profile). Intent RSI-eligible. Deviations 6 and 9 recorded |
| 2026-10-05 | Architect decisions applied: commit path, framing, exit codes, planner without model, Gate scope, crash and resume, build order, new stories. A22 merged into A26; A32 to A48 added; open table reduced |
| 2026-10-05 | Two freeze points (prep at launch, planned after requirements). Schemas required for every message. Isolation and user stories added |
