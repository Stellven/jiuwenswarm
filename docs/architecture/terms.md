---
id: arch.terms
type: glossary
level: present
status: draft
version: 1
provides: [arch.terms]
depends_on: [flow.md, capsule/capsule.md]
tags: [terms, start-here]
prd: [4.1.1, 4.2.1, 4.4]
---

# Terms: what is a capsule, and where each term is defined

PRD: 4.1.1, 4.2.1, 4.4

> Answers: which pieces are capsules, and where is each key term defined?

> **Naming note:** names for capsules, nodes, steps, types, records and files in these docs are working names. They will be consolidated into one naming scheme with the PRD and the coding side. Until then, use the names as written here and expect renames.

Definitions live next to the item they name, in a `Key terms` section on that item's page. This page keeps the capsule classification and the Kubernetes analogues, and generates the index of all terms below.

## Capsule or not

| Piece | Capsule? | Why |
|---|---|---|
| Intent compiler (`research.compile_intent`) | **yes** | governed model-backed work, reusable, independently admitted |
| Requirement compiler (`research.compile_brief`) | **yes** | same |
| Research work capabilities (search, screening, hypothesis, POC, benchmark, evaluation, report writing) | **yes** | same. See [capabilities](capabilities/README.md) |
| Search operators (`op.*`) | **yes** | reused by several callers; mediate external or repository access |
| <a id="term-verifier-research-verifier-yes"></a>**Verifier** (`research.verifier`) | **yes** | a CC. It assesses a node's result. Gate host code decides; the verifier only assesses. |
| Planner | no | service that emits the fixed-template DAG in M1 (no model call). Not admitted, not RSI-able. |
| Plan validator, binder, freeze | no | deterministic control code |
| Supervisor, runner, Gate host, store | no | fixed hosts. A capsule cannot run or judge itself. The supervisor is the only store writer. |
| Intake | no | validates the request and snapshots resources |
| <a id="term-delivery"></a>**Delivery** | no | ordinary result processing and publication. No Declaration, no RSI. |
| Model bridge / router | no | ordinary service wrapping Codex. Never picks capsules. |
| Admission, library, librarian | no | not steps of a run |

Test for a host: it knows nothing about any stage. If one stage's change needs a host change, the design is wrong.

## Kubernetes analogues

We borrow patterns from Kubernetes but do not use it. Full table: [k8s-lens](k8s-lens.md).

| Our term | Closest k8s idea |
|---|---|
| Declaration, Binding | spec |
| Observation, Verification, release record | status |
| Node | a Pod run with `restartPolicy: Never` |
| Run | a Job with `backoffLimit: 0` |
| Supervisor | a controller with a reconcile loop |
| Admission | admission controller |
| Active alias | a tag that moves while the image digest is fixed |
| Execution profile | PodSecurity level and `securityContext` |
| Model bridge | ambassador sidecar |
| Doctor, `/ready` | readiness probe |

## Term index (generated)

Every key term is defined on the page that is its home, in a `Key terms` section. This index lists each term with its first sentence and a link. Do not edit it. Rebuild with `python _tools/term_tools.py index`.

<!-- generated:term-index -->
| Term | Meaning | Defined on |
|---|---|---|
| **abort_event** | The SwarmFlow engine flag that stops all further turns once set. | [system/lifecycle.md](system/lifecycle.md#term-abort-event) |
| **Acceptance seed** | A numbered check at the end of a capability page, written `cap.<name>.AC-nn`, with a fixed input and expected output. | [system/test-surfaces.md](system/test-surfaces.md#term-acceptance-seed) |
| **activation** | The librarian action that moves the alias to an already admitted exact hash, written as a durable activation SystemRecord. | [capsule/library.md](capsule/library.md#term-activation) |
| **Adapter** | The one module per existing system under `cc/adapters/`, the only place CC code imports agent-core or jiuwenswarm. | [system/integration.md](system/integration.md#term-adapter) |
| **admission** | The only path into the capsule library: mandatory mechanical validation of a Candidate, then an assurance decision by the policy-selected provider, recorded as a Verdict. | [capsule/admission.md](capsule/admission.md#term-admission) |
| **admitted_inactive** | The Standing state of an admitted RSI child: it is in the library but not current, until a person activates it with a separate request. | [capsule/admission.md](capsule/admission.md#term-admitted-inactive) |
| **alias** | The movable pointer from a capability name to the current admitted `decl_hash`. | [capsule/library.md](capsule/library.md#term-alias) |
| **Artifact** | One value that a capsule produced, a person supplied or control code made: its content stored once by hash, plus a record of what the content is and where it came from. | [schemas/artifact.md](schemas/artifact.md#term-artifact) |
| **attempt** | The count of times a dispatch has been reserved, taken from the committed reservation so that interruptions count even without a terminal Observation. | [capsule/runner.md](capsule/runner.md#term-attempt) |
| **Attempt** | One try at executing a step, numbered from 1. | [system/lifecycle.md](system/lifecycle.md#term-attempt) |
| **Attempt directory** | The one writable scratch directory of a single call, owned by that capsule's child process. | [isolation.md](isolation.md#term-attempt-directory) |
| **benchmark_payload** | The baseline and treatment samples with their raw evidence, collected by Benchmark without any scientific grading. | [types/benchmark-payload.md](types/benchmark-payload.md#term-benchmark-payload) |
| **Binder** | The deterministic step that resolves each planned node to an exact admitted capsule version in the run's library snapshot and attaches its Gate. | [system/planner.md](system/planner.md#term-binder) |
| **Binding** | The pin for one call site of a run: exactly one capsule version by hash, the Verdict that admitted it, the checks the Gate runs on its output, its budget and the judge it may use. | [schemas/binding.md](schemas/binding.md#term-binding) |
| **Block** | A bounded behavior with inputs, outputs, failure semantics and an executable check; the unit coders build. | [system/modules.md](system/modules.md#term-block) |
| **BLOCK** | The verification level for one block, paired with unit design. | [v-model.md](v-model.md#term-block) |
| **BLOCKED** | A check that could not run, for example because a service is missing. | [decisions.md](decisions.md#term-blocked) |
| **body** | The list of every file of a multi-file capability (such as a skill folder), each hashed. | [capsule/fields.md](capsule/fields.md#term-body) |
| **Boundary** | The place where two blocks or processes talk, through a request def and a result def. | [system/modules.md](system/modules.md#term-boundary) |
| **BOUNDARY** | The verification level for one boundary between blocks, paired with interfaces. | [v-model.md](v-model.md#term-boundary) |
| **Boundary sheet** | The generated sheet for one module boundary: sender, receiver, transport, request and result defs, a real valid message, a real rejected message and what each side does on failure. | [contracts/principles.md](contracts/principles.md#term-boundary-sheet) |
| **broker** | The one place inside the runner where `needs.external` is enforced: every nested call to another capsule and every model call goes through it. | [capsule/runner-broker.md](capsule/runner-broker.md#term-broker) |
| **Call** | A request and its result between two modules. | [contracts/principles.md](contracts/principles.md#term-call) |
| **Candidate** | A submission to admission: a Declaration, the files it points at, its tests, how it was built and where it came from. | [schemas/candidate.md](schemas/candidate.md#term-candidate) |
| **Capability Capsule** | One capability the system can run, described by its Declaration and pointing at its code by hash. | [capsule/capsule.md](capsule/capsule.md#term-capability-capsule) |
| **capsule kind** | How a capsule runs, not what job it does: `tool`, `skill`, `prompt_section`, or the unchecked `mcp`, `a2a`, `subagent`, `agent_template` and `composite`; M1 checks the first three. | [capsule/capsule.md](capsule/capsule.md#term-capsule-kind) |
| **carrier** | The single code file, hashed, that a capsule points at by path and symbol, used when the code imports no unpinned local module. | [capsule/fields.md](capsule/fields.md#term-carrier) |
| **CcBackend** | The supervisor-side Swarmflow backend that sends each node to the runner, then calls the Gate host, and only then lets the engine release the node. | [capsule/runner-broker.md](capsule/runner-broker.md#term-ccbackend) |
| **CcHalt** | The exception the generic plan script raises when a step halts. | [system/lifecycle.md](system/lifecycle.md#term-cchalt) |
| **check** | One runnable test of one target (a port or a type), anchored as `deterministic` (code), `reference` (a known answer) or `judged` (a model or person). | [capsule/fields.md](capsule/fields.md#term-check) |
| **check runner** | The trusted code that runs a Check's pinned runner and returns a CheckResult; the Gate host uses it for Tier 1 and admission uses it for test cases. | [capsule/gate-host.md](capsule/gate-host.md#term-check-runner) |
| **closed type** | A payload type whose objects refuse any field the page does not name. | [types/types.md](types/types.md#term-closed-type) |
| **code_hits** | Ordered verbatim Python source locations produced by CodeSearch, each resolving against an authorized immutable project snapshot. | [types/code-hits.md](types/code-hits.md#term-code-hits) |
| **code_sha256** | The hash of a capsule's code that the loader checks before every call: the carrier hash, the hash of the sorted body list, or the hash of the pinned remote or members. | [capsule/fields.md](capsule/fields.md#term-code-sha256) |
| **Codex adapter** | The CC adapter (`cc/adapters/codex.py`) that wraps the existing Codex subscription service for the model bridge. | [system/integration.md](system/integration.md#term-codex-adapter) |
| **Commit batch** | A set of records published together by one atomic commit, for example all Bindings of a phase. | [system/storage.md](system/storage.md#term-commit-batch) |
| **ConfigSnapshot** | The effective configuration after layering packaged defaults, user config and project config, with its provenance and sha256. | [system/environment.md](system/environment.md#term-configsnapshot) |
| **confinement** | Running generated code in a restricted, unprivileged process that can reach only its authorized workspace, with no network egress. | [capsule/process-boundary.md](capsule/process-boundary.md#term-confinement) |
| **Confinement** | The mechanism that limits a restricted child to its input snapshots and one attempt directory, with no network and no credentials. | [isolation.md](isolation.md#term-confinement) |
| **Data Foundation** | The evidence layer that captures required raw execution evidence as it happens and later assembles and exports records. | [system/storage.md](system/storage.md#term-data-foundation) |
| **decl_hash** | The hash of the whole Declaration with every default filled in, computed by admission. | [capsule/fields.md](capsule/fields.md#term-decl-hash) |
| **Declaration** | The contract one capability declares: what it takes, gives, needs, changes and promises, and what RSI may change. | [capsule/fields.md](capsule/fields.md#term-declaration) |
| **Declaration-derived test** | The test a trusted builder compiles for each node from its producer's Declaration plus host policy and places directly after the node. | [verification.md](verification.md#term-declaration-derived-test) |
| **delivery** | The ordinary module that renders `research_report.md` and the POC zip deterministically, copies them into `outputs/<run_id>/` and records what it wrote. | [capabilities/delivery.md](capabilities/delivery.md#term-delivery) |
| **Demo** | A runnable milestone D0 to D6 that ends a build step and shows one capability working end to end, for example a work capsule followed by its Gate. | [build-order.md](build-order.md#term-demo) |
| **dependency_assessment** | The deterministic policy result for one dependency requirement under one frozen dependency-registry version. | [types/dependency-assessment.md](types/dependency-assessment.md#term-dependency-assessment) |
| **dependency_requirement** | A model, package or dataset identity that an opportunity says it needs, before policy decides whether it is available. | [types/dependency-requirement.md](types/dependency-requirement.md#term-dependency-requirement) |
| **Derived view** | A rebuildable projection such as `records.jsonl`, a scorecard or an export. | [system/storage.md](system/storage.md#term-derived-view) |
| **Deviation** | A place where the design deliberately differs from the PRD, listed with what the PRD says, what we do and what is still respected. | [decisions.md](decisions.md#term-deviation) |
| **dispatch** | The caller kind for a workflow node's call (the others are `gate`, `admission` and `nested`). | [capsule/runner-broker.md](capsule/runner-broker.md#term-dispatch) |
| **Dispatch** | The supervisor sending one step to the runner after it has reserved the call. | [system/records.md](system/records.md#term-dispatch) |
| **dispatch_id** | The id of one dispatch, derived deterministically from run, step, Binding hash, input hashes and attempt. | [system/records.md](system/records.md#term-dispatch-id) |
| **Doctor** | The check run before every run that reports the platform, dependencies and security profile as a `DoctorReport`. | [system/environment.md](system/environment.md#term-doctor) |
| **effect class** | The author's promise about state and undo: `pure`, `read_only`, `idempotent`, `compensable`, `nonrepeatable_effect` or `irreversible`. | [capsule/fields.md](capsule/fields.md#term-effect-class) |
| **effects** | The list of changes a capsule makes to the world, each with the resource it touches, its scope, whether it is idempotent and whether it can be undone. | [capsule/fields.md](capsule/fields.md#term-effects) |
| **epoch** | One immutable version of the Policy. | [schemas/policy.md](schemas/policy.md#term-epoch) |
| **evaluation_verdict** | The scientific classification of the results, with its supporting comparisons. | [types/evaluation-verdict.md](types/evaluation-verdict.md#term-evaluation-verdict) |
| **Event bus** | The in-process channel (`cc.events.emit`, `cc.events.subscribe`) on which the CC hosts announce what they do. | [system/observability.md](system/observability.md#term-event-bus) |
| **evidence_bundle** | The bounded package a judge is shown: the criteria or rubrics, the producer's promises, and the admitted input and output values as text. | [types/evidence-bundle.md](types/evidence-bundle.md#term-evidence-bundle) |
| **EvidenceRef** | A small shape `{evidence_type, reference, description, metadata}` that points at what shows a claim, such as an Observation id or a URI. | [schemas/common.md](schemas/common.md#term-evidenceref) |
| **evolution** | The Declaration section that says whether RSI may build new versions of this capsule (`rsi`: none, propose or submit) and which parts it may change (`may_change`). | [capsule/fields.md](capsule/fields.md#term-evolution) |
| **ExecutionProfile** | The pinned execution limits of a call: platform, process identity, readable and writable roots, network, credentials, IPC, resource limits and model-call limits. | [schemas/profiles.md](schemas/profiles.md#term-executionprofile) |
| **exempt** | The assurance level Puppet admission grants to an allowlisted hash after mandatory validation. | [capsule/admission.md](capsule/admission.md#term-exempt) |
| **ext** | The one open field of a record or payload: a map keyed by tool or producer for extra data. | [schemas/common.md](schemas/common.md#term-ext) |
| **Finding** | A typed, never-edited observation about capsules, judges or an unmet need, such as a measured cost, a judge calibration or the invalidation of a Verdict. | [schemas/finding.md](schemas/finding.md#term-finding) |
| **Fixed outer flow** | The positions that always exist in a run: intake, intent and Gate, requirements and Gate, planner, validate and bind and freeze, dispatch and delivery. | [flow.md](flow.md#term-fixed-outer-flow) |
| **Fixture** | Immutable fixed input bytes or a fake neighbour used to exercise a block or boundary without live services. | [system/test-surfaces.md](system/test-surfaces.md#term-fixture) |
| **fixture oracle** | The private service that alone reads hidden RSI fixtures and per-case results, runs parent and child in fresh confined processes, and returns only aggregate outcomes. | [capsule/fixture-oracle.md](capsule/fixture-oracle.md#term-fixture-oracle) |
| **Frame** | One length-prefixed JSON message in a stream between two processes. | [contracts/principles.md](contracts/principles.md#term-frame) |
| **Freeze** | Publishing one phase's plan and Bindings as one atomic batch so nothing changes afterwards. | [system/lifecycle.md](system/lifecycle.md#term-freeze) |
| **Gate** | The check placed right after a work node that stops or releases control flow. | [verification.md](verification.md#term-gate) |
| **Gate host** | Control code, not a capsule, that checks one finished dispatch or nested call: it runs the deterministic checks itself, asks the verifier for the judged ones, folds all results by policy and writes th | [capsule/gate-host.md](capsule/gate-host.md#term-gate-host) |
| **gate verdict** | One of `PASS`, `PASS_WITH_KNOWN_LIMITATIONS`, `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE`, computed once by the Gate host and stored in the Verification. | [capsule/gate-host.md](capsule/gate-host.md#term-gate-verdict) |
| **GateProfile** | The pinned set of deterministic, semantic and evidence rules, and the actions for each result, that a Gate applies at one call site. | [schemas/profiles.md](schemas/profiles.md#term-gateprofile) |
| **guarantees** | The Declaration section for what a capsule promises: its checks, optional failure modes and an optional quality target. | [capsule/fields.md](capsule/fields.md#term-guarantees) |
| **Halt** | A failed Gate, failed commit, timeout or denied effect stops all further dispatch for the run, siblings included. | [system/lifecycle.md](system/lifecycle.md#term-halt) |
| **halt_report** | The record the supervisor writes when a run halts, giving the failing step, the exact evidence, the reason and the permitted human action. | [system/lifecycle.md](system/lifecycle.md#term-halt-report) |
| **hard_requirement** | The setting that makes Landlock mandatory: if confinement cannot start with it, the call fails with `UNSUPPORTED_SECURITY_PROFILE` instead of running without it. | [isolation.md](isolation.md#term-hard-requirement) |
| **Headless** | Configuration `cc.execution.headless`, default false. | [system/lifecycle.md](system/lifecycle.md#term-headless) |
| **Helper** | A small shared building block, such as `ref`, `id`, `hash` or a nested part of a bigger message. | [contracts/principles.md](contracts/principles.md#term-helper) |
| **hidden final set** | The hidden fixtures held by the custodian and scored only once per session, after close, to decide whether the best child is promotable. | [capsule/fixture-oracle.md](capsule/fixture-oracle.md#term-hidden-final-set) |
| **hidden loop set** | The hidden fixtures used to score proposals during an RSI session, authored by someone other than the capsule builder. | [capsule/fixture-oracle.md](capsule/fixture-oracle.md#term-hidden-loop-set) |
| **human_session** | The native agent-core session that the halt host opens (through `cc.adapters.local_session`) so a person can review a halt and reply. | [system/lifecycle.md](system/lifecycle.md#term-human-session) |
| **hypothesis_blueprint** | The pre-registered claim, methods, resources and thresholds of the hypothesis, fixed before any experiment runs. | [types/hypothesis-blueprint.md](types/hypothesis-blueprint.md#term-hypothesis-blueprint) |
| **idea_set** | The output of Search and Ideation: the queries run, the verbatim evidence found grouped by query, and one to three candidate ideas, each citing its evidence. | [types/idea-set.md](types/idea-set.md#term-idea-set) |
| **Idempotency** | Repeating a call with the same `request_id` and the same canonical bytes returns the same result or in-progress. | [contracts/principles.md](contracts/principles.md#term-idempotency) |
| **intake** | The user's request and the extracted text of their reference documents as one value. | [types/intake.md](types/intake.md#term-intake) |
| **IntentIR** | What the user's prompt asks for, split into goals, outcomes, constraints, open questions, contradictions and unknowns. | [types/intent-ir.md](types/intent-ir.md#term-intentir) |
| **interface_hash** | The hash of only what a test depends on (name, kind, ports, preconditions, effect class and each check's identity). | [capsule/fields.md](capsule/fields.md#term-interface-hash) |
| **jiuwenbox** | The existing sandbox service (Bubblewrap, Landlock, seccomp, network isolation, cgroup limits) that we reuse as the confinement engine. | [isolation.md](isolation.md#term-jiuwenbox) |
| **Landlock** | A Linux kernel feature that limits which paths a process may use. | [isolation.md](isolation.md#term-landlock) |
| **library snapshot** | The frozen, hashed list of exact capability versions (name, `decl_hash`, `interface_hash`, Verdict and Standing refs) that one run is pinned to at launch. | [capsule/library.md](capsule/library.md#term-library-snapshot) |
| **lineage** | Where a version came from: its parent's `decl_hash` and how it relates to it (supersedes, specialises, merges, migrated_from). | [capsule/fields.md](capsule/fields.md#term-lineage) |
| **may_change** | The list of Declaration field paths or `files:` globs that an RSI child may change; everything else must stay as in the parent. | [capsule/fields.md](capsule/fields.md#term-may-change) |
| **Message family** | The kind every message def belongs to: Call, Record, Event, Frame, Profile, Report or Helper. | [contracts/principles.md](contracts/principles.md#term-message-family) |
| **Model bridge** | The only code that holds model credentials and talks to the Codex app-server. | [system/model-bridge.md](system/model-bridge.md#term-model-bridge) |
| **Model routing** | The ordinary module that picks the model endpoint for a model request. | [model-routing/README.md](model-routing/README.md#term-model-routing) |
| **Model turn** | One blocking prompt-and-reply exchange through the bridge. | [system/model-bridge.md](system/model-bridge.md#term-model-turn) |
| **needs** | The Declaration section for what must hold before a call and what the capsule uses: preconditions, dependencies on other capsules, network, packages, secrets and resources. | [capsule/fields.md](capsule/fields.md#term-needs) |
| **Node** | One use of a Capability Capsule for one task, bound into a frozen run plan with its exact version, actual inputs, limits and Gate. | [system/nodes.md](system/nodes.md#term-node) |
| **NOT_RUN** | A check that was never run. | [decisions.md](decisions.md#term-not-run) |
| **obs_id** | The Observation's own id, and the one join key for everything inside a capsule call: Artifacts, captures, nested and judge calls. | [system/observability.md](system/observability.md#term-obs-id) |
| **Observation** | One record per reserved capsule call: who called it, the pinned version, inputs by reference, precondition results, outcome and reason, time, cost and model. | [schemas/observation.md](schemas/observation.md#term-observation) |
| **operator** | A small reusable `op.*` capsule that a work capsule calls as a nested call through the broker, such as a search or code-search helper. | [capabilities/README.md](capabilities/README.md#term-operator) |
| **opportunity_card** | The winning consolidated opportunity with its evidence references, plus the ordered scores and dispositions of every consolidated candidate. | [types/opportunity-card.md](types/opportunity-card.md#term-opportunity-card) |
| **ordinary module** | Control code with no Declaration, no RSI and no Gate, kept as plain code because nothing needs it to be an independently governed capability. | [capabilities/README.md](capabilities/README.md#term-ordinary-module) |
| **parent and child** | The parent is the admitted capsule version being improved; the child is the new immutable Candidate RSI builds from it. | [capsule/rsi.md](capsule/rsi.md#term-parent-and-child) |
| **payload type** | The type of a value that one module hands to another, such as the user's request, an IntentIR or a Research Brief. | [types/types.md](types/types.md#term-payload-type) |
| **PENDING_DESIGN** | A design choice we have not made yet. | [decisions.md](decisions.md#term-pending-design) |
| **PENDING_SOURCE** | An input we need from the PRD, the coding side or an external team and do not have. | [decisions.md](decisions.md#term-pending-source) |
| **Phase** | One of the two plan stages of a run: `prep` (intent and requirement steps) or `planned` (the planner's task nodes). | [system/lifecycle.md](system/lifecycle.md#term-phase) |
| **phase** | Which of a run's two plans a `run_plan` is: `prep` or `planned`. | [types/run-plan.md](types/run-plan.md#term-phase) |
| **Plan validator** | A pure function that checks a whole proposed DAG for wrong ports, cycles, permissions, budgets, missing objective coverage and missing Gates. | [system/planner.md](system/planner.md#term-plan-validator) |
| **Planned node** | A task node the planner emitted from the accepted requirements, for example search, screening or POC. | [system/nodes.md](system/nodes.md#term-planned-node) |
| **Planned plan** | The validated and bound DAG of task nodes the planner emitted. | [system/lifecycle.md](system/lifecycle.md#term-planned-plan) |
| **planned plan** | The second plan, proposed by the planner after requirements are accepted, then validated, bound and frozen in the same run. | [types/run-plan.md](types/run-plan.md#term-planned-plan) |
| **Planner** | An ordinary service that proposes the DAG of task nodes. | [system/planner.md](system/planner.md#term-planner) |
| **planted child** | A deliberately built known-bad or known-good child variant (10 bad, 3 good) that the comparator must reject or adopt as expected before optimization is enabled. | [capsule/fixture-oracle.md](capsule/fixture-oracle.md#term-planted-child) |
| **poc_bundle** | The immutable four-file bundle of generated proof-of-concept code (patch, harness and requirements) assembled before any execution. | [types/poc-bundle.md](types/poc-bundle.md#term-poc-bundle) |
| **Policy** | A named policy document holding every "how": required fields, rules, defaults, thresholds, mappings and the values of every open list. | [schemas/policy.md](schemas/policy.md#term-policy) |
| **port** | One named input or output of a capsule, with a port type. | [capsule/fields.md](capsule/fields.md#term-port) |
| **port type** | A type name that ports and checks use, with the schema a value must match and the checks every value of that type must pass. | [schemas/port-types.md](schemas/port-types.md#term-port-type) |
| **Prep plan** | The fixed list of preparation steps (intent, then requirement) with their Bindings and Gate profiles. | [system/lifecycle.md](system/lifecycle.md#term-prep-plan) |
| **prep plan** | The fixed first plan, frozen at launch: the intent step, then the requirement step, each with its Gate. | [types/run-plan.md](types/run-plan.md#term-prep-plan) |
| **Preparation node** | A node from the fixed prep plan: the intent call or the requirement call. | [system/nodes.md](system/nodes.md#term-preparation-node) |
| **Probe** | A doctor test that tries something a confined child must not be able to do, such as reading credentials, the store or fixtures. | [system/environment.md](system/environment.md#term-probe) |
| **ProfileRef** | A reference `{kind, id, sha256}` to one immutable policy profile of kind `admission`, `gate`, `retry` or `execution`. | [schemas/profiles.md](schemas/profiles.md#term-profileref) |
| **provisional** | The assurance level `tested_admission` grants after the visible suites actually ran and passed. | [capsule/admission.md](capsule/admission.md#term-provisional) |
| **publication manifest** | The record of every published file with its relative path, hash, size and source reference, checked deterministically by delivery. | [capabilities/delivery.md](capabilities/delivery.md#term-publication-manifest) |
| **Puppet admission** | A developer-decision admission provider for exact allowlisted `decl_hash` values: it runs mandatory validation but no assurance suite, and may grant `exempt`. | [capsule/admission.md](capsule/admission.md#term-puppet-admission) |
| **quota** | The durable limit on loop queries, reserved before a query runs. | [capsule/fixture-oracle.md](capsule/fixture-oracle.md#term-quota) |
| **reason code** | An `UPPER_SNAKE` code, such as `CARRIER_CHANGED`, that says why something failed or moved. | [schemas/policy.md](schemas/policy.md#term-reason-code) |
| **Record vs event** | A record is a durable fact in the store and is the authority. | [system/observability.md](system/observability.md#term-record-vs-event) |
| **referee** | The fixed code and the one verifier capsule that decide what passing means, protected from RSI. | [capsule/trust.md](capsule/trust.md#term-referee) |
| **registry** | An open list of allowed values for a `reg(...)` field, kept in the Policy. | [schemas/policy.md](schemas/policy.md#term-registry) |
| **Release** | The committed record that lets a node's successors run. | [system/lifecycle.md](system/lifecycle.md#term-release) |
| **Report** | A read-only summary a tool or the supervisor produces, such as a doctor report. | [contracts/principles.md](contracts/principles.md#term-report) |
| **request_id** | The id every `_request` def requires and every result echoes. | [contracts/principles.md](contracts/principles.md#term-request-id) |
| **Research Brief** | The contract every later stage reads: the research objective, scope, constraints, prioritised requirements and acceptance metrics. | [types/research-brief.md](types/research-brief.md#term-research-brief) |
| **research_report** | The final Markdown report: findings, method, benchmark analysis, the verdict and its limitations, and verified citations. | [types/research-report.md](types/research-report.md#term-research-report) |
| **Reservation** | The `dispatch_reserved` system record the supervisor commits before any effect. | [system/records.md](system/records.md#term-reservation) |
| **resource snapshot** | A read-only repository, document, dataset or validation resource after the launcher or store has frozen its identity for one run. | [types/resource-snapshot.md](types/resource-snapshot.md#term-resource-snapshot) |
| **restricted child** | The unprivileged process started under the fixed profile to run generated POC code. | [capsule/process-boundary.md](capsule/process-boundary.md#term-restricted-child) |
| **Restricted child** | A capsule or POC process run as a separate non-root identity with a private network namespace, no credentials, no store, no fixtures and one writable attempt directory. | [isolation.md](isolation.md#term-restricted-child) |
| **Resume** | A human command that continues the same frozen run after review. | [system/lifecycle.md](system/lifecycle.md#term-resume) |
| **RetryProfile** | The pinned retry rule of a call. | [schemas/profiles.md](schemas/profiles.md#term-retryprofile) |
| **rollback** | An activation request that points the alias at a historical admitted hash. | [capsule/library.md](capsule/library.md#term-rollback) |
| **routing_action** | What the run does after a gate verdict: `ADVANCE`, `HALT` or `ESCALATE_TO_HUMAN`. | [capsule/gate-host.md](capsule/gate-host.md#term-routing-action) |
| **RoutingDecision** | The closed result of `select`, naming the route id and selected model. | [model-routing/README.md](model-routing/README.md#term-routingdecision) |
| **RoutingRequest** | The closed run-scoped request to `select`, with run, step, attempt, `obs_id`, capsule, required capabilities and the model allowlist. | [model-routing/README.md](model-routing/README.md#term-routingrequest) |
| **RSI** | Recursive self-improvement: the offline, separate area that proposes bounded changes to one eligible work capsule. | [rsi.md](rsi.md#term-rsi) |
| **RSI target** | The one capsule part an offline RSI session is allowed to improve: a permitted implementation file, the Screening prompt and rubric text, or `research.compile_intent`. | [capsule/rsi.md](capsule/rsi.md#term-rsi-target) |
| **rubric** | The pinned criteria text or code behind a judged check. | [capsule/fields.md](capsule/fields.md#term-rubric) |
| **Run** | One execution of a research request from launch to delivery or halt, named by its `run_id`. | [system/lifecycle.md](system/lifecycle.md#term-run) |
| **Run bundle** | The raw execution capture of one call, kept under `records/bundles/<run_id>/<obs_id>/` and completed by an immutable manifest. | [system/storage.md](system/storage.md#term-run-bundle) |
| **run_id** | The id of one run, created at launch. | [system/records.md](system/records.md#term-run-id) |
| **run_plan** | The control flow of one run as data: the steps in order, each naming its work capsule, its gate capsule and where each input comes from. | [types/run-plan.md](types/run-plan.md#term-run-plan) |
| **runner** | The only code that runs a capsule: it checks the exact code by hash, binds inputs, calls the capsule by its kind, and returns Artifacts and an Observation. | [capsule/runner.md](capsule/runner.md#term-runner) |
| **screening_assessments** | The model-backed screening capsule's structured assessments, before deterministic filtering, scoring and ranking. | [types/screening-assessments.md](types/screening-assessments.md#term-screening-assessments) |
| **Seam** | An API between two modules that are built separately. | [system/seams.md](system/seams.md#term-seam) |
| **search_hits** | The ranked sources one query found, with the verbatim passages that matched. | [types/search-hits.md](types/search-hits.md#term-search-hits) |
| **seccomp** | A Linux kernel filter that limits the system calls a process may make. | [isolation.md](isolation.md#term-seccomp) |
| **session** | One offline RSI run by a developer from frozen evidence, pinning the parent, model, settings, policy, corpus and permitted paths. | [capsule/rsi.md](capsule/rsi.md#term-session) |
| **singleton** | The most common capsule form: one capability as a one-node graph whose node is its own code. | [capsule/fields.md](capsule/fields.md#term-singleton) |
| **source_text** | Text with a stable source and offset basis: the smallest independent text input for language capabilities. | [types/source-text.md](types/source-text.md#term-source-text) |
| **StageContext** | The bounded, read-only view of earlier run evidence the supervisor hands the report capability: references and short summaries of accepted outputs, scoped to the current call. | [capabilities/write-report.md](capabilities/write-report.md#term-stagecontext) |
| **STALE** | A check result recorded against an older revision of the thing it checks. | [decisions.md](decisions.md#term-stale) |
| **Standing** | The one moving pointer in the library: for each capsule name, which version is current and in what state (`admitted`, `admitted_inactive`, `deprecated`, `suspect`, `retired`, `revoked`). | [schemas/standing.md](schemas/standing.md#term-standing) |
| **Step** | A position in a frozen plan, named by its `step_id`. | [system/nodes.md](system/nodes.md#term-step) |
| **step_id** | The id of one step within a run's plan. | [system/records.md](system/records.md#term-step-id) |
| **Supervisor** | The trusted process that freezes plans, reserves dispatches, calls the runner and the Gate host, commits records and releases nodes. | [system/lifecycle.md](system/lifecycle.md#term-supervisor) |
| **SwarmFlow** | The agent-core workflow engine we reuse. | [system/integration.md](system/integration.md#term-swarmflow) |
| **SYSTEM** | The verification level for the whole integrated system, paired with architecture and requirements. | [v-model.md](v-model.md#term-system) |
| **SystemRecord** | A durable control record the supervisor writes (run phase, dispatch reservation, release, human review, RSI and oracle records). | [system/records.md](system/records.md#term-systemrecord) |
| **SystemRef** | A reference `{id, sha256}` to one SystemRecord. | [system/records.md](system/records.md#term-systemref) |
| **test case** | One input and its expected result, written only by admission from a Candidate's tests. | [schemas/checks.md](schemas/checks.md#term-test-case) |
| **test suite** | A hashed set of test cases, visible to the builder or sealed from them. | [schemas/checks.md](schemas/checks.md#term-test-suite) |
| **tested_admission** | The default admission provider: it runs the visible test suites against fixtures and may grant `provisional`. | [capsule/admission.md](capsule/admission.md#term-tested-admission) |
| **Tier 1** | The deterministic checks of a Gate: schema, references, files, provenance, budgets and required evidence. | [verification.md](verification.md#term-tier-1) |
| **Tier 2** | The independent `research.verifier` assessment of claim support, citations, consistency and limits. | [verification.md](verification.md#term-tier-2) |
| **Track** | The label of an execution context: `production`, `offline_rsi` or `isolated_experiment`. | [system/experiments.md](system/experiments.md#term-track) |
| **trial** | One recorded candidate state (parent, proposal or ablation) evaluated by the oracle in an RSI session. | [capsule/fixture-oracle.md](capsule/fixture-oracle.md#term-trial) |
| **TrialRef** | A private `{id, sha256}` reference to a trial. | [capsule/fixture-oracle.md](capsule/fixture-oracle.md#term-trialref) |
| **UNSUPPORTED_SECURITY_PROFILE** | The reason code returned when the restricted-child engine cannot start with the required settings, for example without Landlock. | [system/deployment.md](system/deployment.md#term-unsupported-security-profile) |
| **V row** | One row of the verification table, ids V01 and up, naming a check, its level and its observation point. | [system/test-surfaces.md](system/test-surfaces.md#term-v-row) |
| **Verdict** | Admission's decision on one Declaration under one policy epoch and port type vocabulary, with its reasons and evidence. | [schemas/verdict.md](schemas/verdict.md#term-verdict) |
| **Verification** | The Gate host's record of checking one governed call's live output: each check's result and the folded decision pass, fail or blocked. | [schemas/verification-record.md](schemas/verification-record.md#term-verification) |
| **verifier** | The one shared judge capsule (`research.verifier`, kind `skill`) that every Gate reuses through a pinned Gate profile. | [capsule/gate-capsules.md](capsule/gate-capsules.md#term-verifier) |
| **verifier_assessment** | The judge's answer for each criterion of an evidence bundle, with a rationale and exact quotations. | [types/verifier-assessment.md](types/verifier-assessment.md#term-verifier-assessment) |
| **work capsule** | A capsule that produces a stage's output, such as `research.compile_brief` or `research.build_poc`, as opposed to the verifier that judges it. | [capabilities/README.md](capabilities/README.md#term-work-capsule) |
<!-- /generated:term-index -->
