---
type: design
status: draft
version: 1
owner: muk
tags: [capsule, tooling, m1]
provides: [cc.tooling_map, cc.field_enforcement_map]
depends_on: [fields.md, stages.md, runner.md, toolchain.md, permissions.md, library.md]
---

# CC Tooling and Field Enforcement

> **Draft design.** This page owns the CC tool inventory, M1 versus deferred tool boundary, and the map from Declaration fields to their validation and runtime enforcement. It does not redefine schemas or tool APIs: [Declaration](fields.md) owns field meaning and M1 status, [stages](stages.md) owns checked/unchecked classification, [runner](runner.md) owns call execution, and [toolchain](toolchain.md) owns tool APIs and record writes. A field marked `checked` is a design/test commitment; it does not by itself prove that every runtime path enforces it.

CC is a schema; tools perform authoring, admission, execution, checking, storage, and later library operations. These tools are not nodes of a run, so they are not capsules; a gate or verifier invoked during a run may be a capsule. This page answers two architecture questions: which tools are in the M1 path, and what actually checks each Declaration field.

**Needed for M1** means the M1 architecture depends on the tool's contract. It does not mean every runtime mechanism behind the tool already exists. An item marked deferred is outside the current contract unless an open issue makes it a prerequisite for a specific stage. Unchecked fields and their later consumers are listed in the [unlocks](stages.md#what-the-unchecked-fields-unlock) table.

**Builds on** names existing jiuwenswarm or agent-core pieces cited for possible reuse. jiuwenswarm paths are under `jiuwenswarm/jiuwenswarm/` at `bf0e8af7` and have not been rechecked against current checkout (`6cc05c36b`). agent-core paths were read at `e23806c1`; pin `9e339019` is available locally, but [permissions](permissions.md) says only its `file_guard` row has been rechecked so far. Reuse claims need source verification before implementation. "None found" means the reviewed sources named no reusable piece.

## The tools

| Tool | Reads | Writes | Needed for M1 | Builds on |
|---|---|---|---|---|
| **Author kit** | a draft Declaration, its files, its tests, the [policy](../schemas/policy.md) | nothing stored: a report for the author | needed | none found |
| **Admission** | a [Candidate](../schemas/candidate.md), the policy | [Verdict](../schemas/verdict.md), [Standing](../schemas/standing.md), test cases and test suites, Artifacts for test inputs and fixtures, stored files | needed | none found |
| **Runner** | the [Binding](../schemas/binding.md), the Declaration, the code by hash | [Artifact](../schemas/artifact.md), [Observation](../schemas/observation.md) | needed | Swarmflow's `agent()` (agent-core `agent_teams/workflow/engine/primitives.py`); on the DeepAgent (harness) path only, the permission rail (below) and `RailManager` (`agents/harness/common/plugins/rail_manager.py:52`), which registers custom rails (hooks) on the DeepAgent |
| **Permission controls** | the Binding's Declaration: `effect_class`, `effects`, `needs.network`, `needs.external`, `needs.human_interaction` | runner decision/refusal; host permission rules where that rail is active; process containment where specifically provided ([permissions](permissions.md), [process boundary](process-boundary.md)) | runner's explicit M1 decisions required; complete OS/network mediation remains an open design gap | agent-core `PermissionEngine`, `file_guard`, `net_guard`; jiuwenbox `SecurityPolicy` (future general sandbox) |
| **M1 generated-code process boundary** | a gated `poc_bundle`, run/profile context, a constrained program request | process outcome and references to execution evidence; see [process boundary](process-boundary.md) | required by PRD 3.7 and 5.4.3; contract is provisional and blocks benchmark readiness | new boundary; do not equate it with jiuwenbox |
| **RSI fixture oracle** | an RSI candidate ref and session id; oracle privately selects its hidden suite | aggregate-only pass/fail counts; see [fixture oracle](fixture-oracle.md) | required for RSI's hidden-fixture path; API and trust boundary are provisional | new service; separate from admission checks and benchmark execution |
| **Check runner and gate** | [checks](../schemas/checks.md), Artifacts, Observations, the Binding, the policy | [Verification](../schemas/verification-record.md); later, Findings of kind `fit_failure` and `use_outcome` (unchecked) | needed | agent-core Symphony `Evaluator` protocol (`symphony/evaluation/base.py`) for check runners |
| **Library store** | everything admission and the runner write | records keyed by id, code keyed by sha256 | needed | agent-core `BaseKVStore` (`exclusive_set`, `get_by_prefix`) and its object store |
| **Dependency watcher** (a librarian job) | the pins in `needs.external` and `needs.dependencies`, upstream releases and advisories | Findings of kind `dependency_update`; `suspect` moves for security | not needed. Unlocks: RSI | none found |
| **Lineage index** | `identity.lineage` of every admitted version | an index from each `decl_hash` to its parent and children | not needed. Unlocks: tracking, merge | none found |
| **Librarian** | Standing, Observations, Verifications, Findings | Standing changes, [Findings](../schemas/finding.md), including kind `measurement` | not needed. Unlocks: librarian | none found |
| **Offline RSI engine and candidate submitter** | parent Declaration/Verdict/suites, allowed mutation scope, offline observations and oracle aggregates | hash-chained attempt evidence and an RSI Candidate submitted through M14 | required by PRD 4.4; CC seam contract is owned by rsi-engine.md | jiuwenswarm RSI service (`agents/harness/common/rsi/`); reuse references need source verification |
| **Selection index** | name, summary, ports, effect class, Standing | an index of admitted capsules for search and for matching by port type; Findings of kind `gap` when no capsule fits | not needed. Unlocks: selection | jiuwenswarm `SkillTaxonomyRuntime` (`symphony/skill_retrieval/runtime.py:30`) over agent-core `AgenticSkillRetrievalToolkit`; agent-core Symphony `CapabilityProvider` (`symphony/interfaces/capability.py`) |
| **Cost meter** | Observations | token and money cost per call, for Binding budgets | not needed; the first epoch budgets time only. Unlocks: budgets | GenAI span attributes (`gen_ai_semconv.py:53-90`) |
| **Importer for outside sources** | a skill, tool, MCP server or A2A agent from a hub, a repo or a local folder | draft Declarations, checks and test cases, and Candidates with `submitted_by.kind: importer` | not needed. Unlocks: importer, remote capsules | `SkillManager` install handlers (`server/runtime/skill/skill_manager.py`); the MCP registry (`server/runtime/mcp/registry.py`); agent-core MCP clients (`core/foundation/tool/mcp/client/`) |
| **General isolated verification sandbox** | a Candidate, dependencies, config, secrets, resource limits and policy | isolated test results, Verdict `environment`, observed effects | Deferred broader facility; PRD 4.1.4 defers jiuwenbox. This does not defer the narrower M1 generated-code process boundary above | jiuwenbox (`jiuwenbox/` at the jiuwenswarm repository root) |
| **Store or registry** | admitted capsules, their Verdicts, Candidate `source` | published capsules with their Declarations | not needed. Unlocks: store | openJiuwen Agentic Hub (`openjiuwen/skillhub`); jiuwenswarm `HubClient` (`server/runtime/marketplace/hub_client.py:150`) |
| **Composer** | Observations of capsules that run in sequence and pass | a Candidate for a `composite` capsule | not needed. Unlocks: composer; see [composition](composition.md) | none found |
| **Remover** | Standing, each effect's `undo` | a Standing change (`retired` or `revoked`), written through the librarian | not needed. Unlocks uninstall. `undo` is text, applied by a person or a later tool | none found |

Needed tools also read unchecked groups once their fields exist: admission reads certification; the runner and gate read retries, fallbacks, quality labels and exempt agents; every tool may write tracing.

## How the M1 tools work

**Author kit.** Authors run it before they submit. It checks a draft Declaration against the schema and the policy's `required` section. It hashes every file, computes `decl_hash` and `interface_hash`, and runs the capsule's admission checks on its test cases. It should share admission's shape and hash code, so that the two agree.

**Admission.** Its steps are on the [library](library.md#admission-the-only-way-in) page.

**Runner.** Its full design is on [runner](runner.md). Every capsule call goes through it. It checks the code against the Binding's hashes, checks preconditions, calls the capsule by its kind, stores each output as an Artifact and writes an Observation. A call with no Observation went around the runner.

**Check runner and gate.** Check runners run the checks on an output: `deterministic` and `reference` checks with no model first, then `judged` checks. The gate adds its own fixed checks, `check.call_ok.v1` and `check.within_budget.v1`, folds all results into `pass`, `fail` or `blocked`, as policy `gates` defines, and writes one Verification for each `dispatch` call.

## For imported capabilities

- The importer drafts the Declaration, the checks and the test cases. A person or the author kit completes them before submission, because admission needs at least one check and a test case for each admission check.
- One MCP server becomes one capsule per tool it exposes. A2A agents come in the same way, as `a2a` capsules pinned by endpoint and version.
- Every capsule named in `needs.external` is imported and admitted first.
- A receiving system re-admits every capsule under its own policy epoch. Another store's Verdict is evidence, not admission.

## What the existing pieces give

- **Permissions and the Codex runtime.** How declarations become permission rules, and why the Codex runtime skips the rail: [permissions](permissions.md).
- **Skill loading.** `SkillManager` already installs skills from online search, ClawHub, SkillNet, team hubs and local folders. An importer would wrap these and add the Declaration and admission. It cannot trust the installed copy's version: a skill's files can change under the same version (`touch_version_metadata`, `server/runtime/skill/archive_store.py:267`, recomputes the checksum and keeps the version). So the hash is taken on a read-only copy.
- **Checksums.** The hub downloader already refuses a package whose SHA-256 differs (`server/runtime/marketplace/hub_package_downloader.py:130`). That proves the download, not the tested code; admission still hashes every file.
- **Sandbox.** jiuwenbox runs tools and code in a Linux sandbox (bubblewrap, Landlock, seccomp, optional network isolation) and keeps audit logs. jiuwenswarm can already send tool execution to it. It would install `needs.dependencies`, inject `needs.secrets` and enforce `needs.resources`.
- **Store.** The Agentic Hub publishes and versions skills, with a ClawHub-compatible API. It stores packages, not Declarations or Verdicts.

## Field validation and enforcement map

The `M1` column is copied conceptually from [fields](fields.md), not re-decided here. “Schema/admission” means shape, cross-field, policy-required, test, or hash validation at authoring/admission. “At call” means the runner or gate enforces a condition during execution. A row can be checked at admission without a corresponding runtime guard; the gap column makes that distinction explicit. Error codes below are the contract only where the owning page defines them; otherwise the owning page's failure table governs.

| Declaration fields | M1 status | Validation / enforcement point | Runtime meaning or remaining gap |
|---|---|---|---|
| Envelope, `schema_version`, `ext`; required fields under policy | Checked fields compiled against grammar; epoch requiredness is policy-controlled | Author kit reports; admission validates schema and active policy | Invalid shape or absent required field is rejected before admission. |
| `identity.name`, `kind`, `summary` | Checked | Admission validates handle/kind and INV-7 summary rule; runner requires a supported kind handler | Unsupported kind cannot run. Summary is a selection description, not execution control. |
| `identity.carrier`, `body` and file hashes; computed `decl_hash`, `interface_hash`, `code_sha256` | Checked | Author kit computes; admission independently recomputes and stores; runner verifies pinned bytes/code at load and on every call | Local code identity is checked. Details and errors belong to [runner](runner.md#from-hash-to-running-code) and [toolchain](toolchain.md#m00d-hashing). |
| `identity.lineage.parent_hash`, `relation` | Checked | Admission resolves parent and applies RSI/change/suite rules | `co_parent_hashes` remains unchecked; merge/composition rules need the future composer. |
| `identity.namespace`, `owner`, `tags`, `license` | Unchecked | Future importer/store/selection consumers | Descriptive and discovery metadata; no M1 admission or run-time effect. |
| `identity.remote` and its pin | Unchecked | No M1 remote admission or execution | Endpoint/version does not prove the service's live fingerprint. Remote capsule support is deferred. |
| `ports.inputs`, `outputs`, `Port.name`, `type`, `description`, `required`, `value_schema`, `check_id` | Checked | Admission checks declarations and required checks; runner binds input names/types and validates output names/types/schema; gate runs the referenced output checks | Call-time mismatch is refused/failed according to [runner](runner.md#one-call-start-to-finish) and [gate](gate-host.md). A declared check is meaningful only if its registry implementation exists. |
| `needs.when` and predicate `id`, `path`, `op`, `value` | Checked | Admission validates predicate shape; runner evaluates against bound inputs and records results | `Predicate.evaluable_at` and `state_source` are unchecked, so unsupported state-root evaluation defers; selection/planning support is not implied. |
| `needs.external`, `ref`, `decl_hash` | Checked | Admission verifies the pinned dependency is admitted; broker/runner refuses a nested capsule call outside the allow-list | Direct in-process calls are only constrained by isolation where isolation is active. `purpose` is unchecked; purpose-aware re-pinning is deferred. |
| `needs.network`, `human_interaction`, `resources.timeout_s` | Checked | Admission validates declaration; runner enforces its explicit unattended-call decision and timeout; host permission rail applies only on backends that run it | This does not imply arbitrary code cannot open sockets. M1's generated POC process has the distinct provisional [process boundary](process-boundary.md); execution coverage is mapped by environment ExecutionProfile and verified by doctor. Other resource dimensions are not enforced generally at M1. |
| `needs.dependencies`, `config`, `secrets`; non-time resource dimensions | Unchecked | Isolated verification/importer design only; not a general M1 execution contract | Dependency installation, config injection, secret delivery, CPU/GPU/memory/disk limits require isolated sandbox support. Do not infer enforcement from fields being present. |
| `changes.effect_class`, `effects` and effect descriptors; `changes.state_kind` | Checked | Admission checks consistency and required fixtures; runner permission checks declared operations where the runtime exposes them | Declaration/consistency check is not complete effect mediation. General undo/reversibility guarantees and automated cross-call drift analysis remain deferred. M1 supported broker/process operations require confinement, capture and comparison to pinned scope/effect authorization before success; unsupported operations are refused. Native permission flags alone do not provide this enforcement. |
| `guarantees.checks` and each Check | Checked | Admission runs admission-time checks on test cases; M10a runs node-time checks; M10 folds results | A missing or unknown check cannot pass. Exact check ports and outcomes are on [check runner/gate](toolchain.md#m10a-check-runner-and-the-check-library) and [gate host](gate-host.md). |
| `guarantees.failure_modes` | Unchecked | Runner can record call errors; declaration-based allow-list, retry/fallback behavior is not an M1 promise | Recording an error does not validate it against this unchecked field. Retries and fallbacks remain deferred. |
| `guarantees.quality` | Unchecked | Future librarian measurement | No M1 target-rate assessment or Standing change from this field. |
| `members`, `wiring` | Unchecked | No M1 composite admission/execution contract | Composition and graph validation require the future composer; don't treat ordinary `needs.external` as a composite graph. |
| `evolution.rsi`, `may_change` | Checked | Admission validates policy permission and child diff; freeze rejects RSI-capable run-control capsules as specified in its API | This restricts admitted changes; it does not implement an RSI engine. `evolution.notes` is unchecked advisory data. |

**Interpretation rule:** “checked” in the schema/status tables means M1 requires/tests the field or rule as defined. The map above distinguishes declaration validation, test-time verification, call-time enforcement, and later observability. Only a runtime control at the actual execution boundary counts as effect enforcement.

## M1 tools versus later tools

| Capability/tool | M1 boundary | API and record authority | Later addition / gap it addresses |
|---|---|---|---|
| Author kit (M13), admission (M14) | Required | [toolchain](toolchain.md#m13-author-kit), [library](library.md#admission-the-only-way-in); author kit reports, admission alone admits and writes library records | Importer can draft candidates from external sources, but cannot waive human confirmation or admission checks. |
| Runner (M04), backend permission controls | Required for the supported run path | [runner](runner.md); runner owns call lifecycle and Observations; permissions owns the declaration mapping | Runner refusals are not OS confinement. Host rails are backend-specific; general effect/network mediation remains open. |
| M1 generated-code process boundary | Required by PRD 3.7 | [process boundary](process-boundary.md); separate contract from the CC capsule-call runner | Concrete profile/API defined; 3.7 execution stays disabled until platform negative probes pass. |
| RSI fixture oracle | Required by the RSI hidden-fixture path in PRD 4.4.9 | [fixture oracle](fixture-oracle.md); sole reader of hidden fixtures, aggregate-only response | Concrete principal/IPC contract in environment; RSI blocks on any failed isolation probe. |
| Offline RSI engine and candidate submission | Required by PRD 4.4 | [RSI](rsi.md), [RSI seam](../seams.md#rsi), [fixture oracle](fixture-oracle.md), [admission](library.md#admission-the-only-way-in) | Offline copy only; one-file code or prompt/rubric mutations, unchanged schemas/referees, attempt log and mainline admission contract are owned by rsi-engine.md. Human activation is required. |
| Check runner (M10a), gate host (M10), verifier/gate capsules | Required | [toolchain](toolchain.md#m10a-check-runner-and-the-check-library), [gate host](gate-host.md); check runner executes, gate owns fold and Verification | Certified tiers are deferred; developer Puppet exempt admission is separately defined and cannot bypass runtime Gates. |
| Store (M12), freeze (M03), launcher (M01), halt host (M03h), hashing (M00d), vocabulary/policy publishers (M00a/M00c) | Required | Their individual APIs and write ownership are on [toolchain](toolchain.md); system diagram is the connected map | None of these should be duplicated by a convenience library or alternate writer. |
| Dependency watcher, lineage index, general librarian | Deferred | No M1 writer/API contract yet | Upstream change findings, lineage traversal and general measured quality. RSI's own attempt log and fixture oracle are distinct M1 requirements, not deferred librarian tools. |
| Selection index, importer, isolated verification, external registry, composer/remover | Deferred | Their future field groups are listed in [stages](stages.md#what-the-unchecked-fields-unlock) | Discoverability/import, safe outside-source onboarding, full composite graph execution, uninstall/undo workflow. |
| Cost meter | Deferred | M1 records time; no token/money budget contract | Observation token/money accounting and budget enforcement. |

## Gaps that must stay visible

1. **M1 generated-code confinement:** stage 3.7 needs the distinct unprivileged process boundary in [process-boundary](process-boundary.md); generic jiuwenbox is deferred and the runner itself is not a sandbox.
2. **Other runtime effect enforcement:** admission checks declarations, but runtime enforcement varies by backend. A design claim that an effect is “enforced” must name the boundary and covered operation classes.
3. **Resource and dependency isolation:** CC reads `timeout_s`; it does not generally install pinned packages, inject secrets, or cap CPU/GPU/memory/disk. Stage 3.7's local POC environment is a special PRD-mandated path, not general Declaration support.
4. **Remote identity:** endpoint/version pins are not a live fingerprint check.
5. **Composite contracts:** `members`/`wiring` remain unchecked and have no M1 composer contract.
6. **Lifecycle tools:** retries, fallbacks, quality measurement, RSI, import, selection, cost budgets and removal each need an owner, API, records, and failure rules before they can be treated as design-complete.

These are architecture gaps, not implementation-algorithm choices. Resolve them by assigning one owning contract page and updating its producers, consumers, gates, seams, and system diagram together.

## Revised handoff owners

The [module/process map](../system/modules.md) is current for code placement. [Environment](../system/environment.md) proposes actual supported-operation confinement, configuration and bridge policy; unsupported profiles fail closed. Admission validates fields; broker authorizes nested/service requests; confined processes enforce filesystem/network access; complete capture records observed effects in required checked Observation.effects_observed and compares them to pinned authorization before success. Automatic librarian drift/Standing action remains deferred. Native permission rails alone are not M1 containment. Required raw capture and model-call counters are M1 requirements; deferred cost estimation/CPU-GPU dashboards do not remove them. [System records](../system/records.md) owns dispatch identity, and [storage](../system/storage.md) owns crash-safe authority. [Offline RSI](rsi-engine.md) and [measurement protocol](../m1/measurement-protocol.md) add the missing required services. No unvalidated profile is called checked enforcement.
