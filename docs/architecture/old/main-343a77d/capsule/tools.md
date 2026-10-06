---
type: capsule
tags: [capsule]
---

# Tools

CC is a schema; tools do the work. Each tool reads the [Declaration](fields.md) or records about a capsule, and writes one kind of record. These tools are not nodes of a run, so they are never capsules; a gate or verifier inside a run may be a capsule. Which fields M1 checks is on [stages](stages.md).

**Needed for M1** says whether M1 needs the tool: **needed** when M1 depends on the checked fields it reads or writes, **not needed** when the tool exists to read unchecked fields. A not-needed tool names its groups in the [unlocks](stages.md#what-the-unchecked-fields-unlock) table, which lists their fields.

**Builds on** names an existing jiuwenswarm or openJiuwen piece the tool could reuse, found in the code. jiuwenswarm paths are under `jiuwenswarm/jiuwenswarm/` at commit `bf0e8af7`. agent-core paths are under `openjiuwen/`, read at `e23806c1`; jiuwenswarm pins `9e339019`, which was not available locally. "None found" means we found nothing to reuse.

## The tools

| Tool | Reads | Writes | Needed for M1 | Builds on |
|---|---|---|---|---|
| **Author kit** | a draft Declaration, its files, its tests, the [policy](../schemas/policy.md) | nothing stored: a report for the author | needed | none found |
| **Admission** | a [Candidate](../schemas/candidate.md), the policy | [Verdict](../schemas/verdict.md), [Standing](../schemas/standing.md), test cases and test suites, Artifacts for test inputs and fixtures, stored files | needed | none found |
| **Runner** | the [Binding](../schemas/binding.md), the Declaration, the code by hash | [Artifact](../schemas/artifact.md), [Observation](../schemas/observation.md) | needed | Swarmflow's `agent()` (agent-core `agent_teams/workflow/engine/primitives.py`); on the DeepAgent (harness) path only, the permission rail (below) and `RailManager` (`agents/harness/common/plugins/rail_manager.py:52`), which registers custom rails (hooks) on the DeepAgent |
| **Permission layer** | the Binding's Declaration: `effect_class`, `effects`, `needs.network`, `needs.external`, `needs.secrets` | per-capsule permission rules, supplied through the permission snapshot, and the sandbox policy ([permissions](permissions.md)) | needed where the permission rail runs (the DeepAgent path); on the Codex runtime the runner and sandbox enforce instead | agent-core `PermissionEngine`, `file_guard`, `net_guard`; jiuwenbox `SecurityPolicy` |
| **Check runner and gate** | [checks](../schemas/checks.md), Artifacts, Observations, the Binding, the policy | [Verification](../schemas/verification-record.md); later, Findings of kind `fit_failure` and `use_outcome` (unchecked) | needed | agent-core Symphony `Evaluator` protocol (`symphony/evaluation/base.py`) for check runners |
| **Library store** | everything admission and the runner write | records keyed by id, code keyed by sha256 | needed | agent-core `BaseKVStore` (`exclusive_set`, `get_by_prefix`) and its object store |
| **Dependency watcher** (a librarian job) | the pins in `needs.external` and `needs.dependencies`, upstream releases and advisories | Findings of kind `dependency_update`; `suspect` moves for security | not needed. Unlocks: RSI | none found |
| **Lineage index** | `identity.lineage` of every admitted version | an index from each `decl_hash` to its parent and children | not needed. Unlocks: tracking, merge | none found |
| **Librarian** | Standing, Observations, Verifications, Findings | Standing changes, [Findings](../schemas/finding.md), including kind `measurement` | not needed. Unlocks: librarian | none found |
| **RSI submitter** | reports from an RSI engine, the parent's Declaration and Verdict | Candidates with `submitted_by.kind: rsi` and `lineage.parent_hash` | not needed. Unlocks: RSI | jiuwenswarm RSI service (`agents/harness/common/rsi/`); agent-core `rsi/` |
| **Selection index** | name, summary, ports, effect class, Standing | an index of admitted capsules for search and for matching by port type; Findings of kind `gap` when no capsule fits | not needed. Unlocks: selection | jiuwenswarm `SkillTaxonomyRuntime` (`symphony/skill_retrieval/runtime.py:30`) over agent-core `AgenticSkillRetrievalToolkit`; agent-core Symphony `CapabilityProvider` (`symphony/interfaces/capability.py`) |
| **Cost meter** | Observations | token and money cost per call, for Binding budgets | not needed; the first epoch budgets time only. Unlocks: budgets | GenAI span attributes (`gen_ai_semconv.py:53-90`) |
| **Importer for outside sources** | a skill, tool, MCP server or A2A agent from a hub, a repo or a local folder | draft Declarations, checks and test cases, and Candidates with `submitted_by.kind: importer` | not needed. Unlocks: importer, remote capsules | `SkillManager` install handlers (`server/runtime/skill/skill_manager.py`); the MCP registry (`server/runtime/mcp/registry.py`); agent-core MCP clients (`core/foundation/tool/mcp/client/`) |
| **Isolated verification sandbox** | a Candidate from outside, its `needs.dependencies`, `needs.config`, `needs.secrets` and `needs.resources`, the policy | test results for admission, Verdict `environment`, the effects observed | not needed. Unlocks: isolated verification | jiuwenbox (`jiuwenbox/` at the jiuwenswarm repository root) |
| **Store or registry** | admitted capsules, their Verdicts, Candidate `source` | published capsules with their Declarations | not needed. Unlocks: store | openJiuwen Agentic Hub (`openjiuwen/skillhub`); jiuwenswarm `HubClient` (`server/runtime/marketplace/hub_client.py:150`) |
| **Composer** | Observations of capsules that run in sequence and pass | a Candidate for a `composite` capsule | not needed. Unlocks: composer; see [composition](composition.md) | none found |
| **Remover** | Standing, each effect's `undo` | a Standing change (`retired` or `revoked`), written through the librarian | not needed. Unlocks uninstall. `undo` is text, applied by a person or a later tool | none found |

Needed tools also read unchecked groups once their fields exist: admission reads certification; the runner and gate read retries, fallbacks, quality labels and exempt agents; every tool may write tracing.

## How the M1 tools work

**Author kit.** Authors run it before they submit. It checks a draft Declaration against the schema and the policy's `required` section. It hashes every file, computes `decl_hash` and `interface_hash`, and runs the capsule's admission checks on its test cases. It should share admission's shape and hash code, so that the two agree.

**Admission.** Its steps are on the [library](library.md#admission-the-only-way-in) page.

**Runner.** Every capsule call goes through it. It checks the code against the Binding's hashes, checks preconditions, calls the capsule by its kind, stores each output as an Artifact and writes an Observation. A call with no Observation went around the runner.

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

## Which tool checks each field

Every field is checked by some tool at some moment, or it is listed here as unenforced. "Admission" includes the author kit, which runs the same checks before submission.

| Field or rule | Checked by | When | If it fails |
|---|---|---|---|
| shape of every field; required fields per epoch | admission | submission | `SCHEMA_NONCONFORMANT` |
| `identity.summary` names no task | admission | submission | `SUMMARY_NAMES_TASK` |
| `identity.name`, `kind` | admission (a known `capsule_kind`); runner (the handler for the kind) | submission; every call | `SCHEMA_NONCONFORMANT` |
| `identity.namespace`, `owner`, `tags`, `license` | importer, store, selection index | import; publishing | none: descriptive only |
| `Port.required`, `Predicate.evaluable_at`, `state_source` | runner (missing required input); planner and selection | every call; planning | `PORT_MISMATCH`; unchecked |
| `evolution.notes` | none: read by builders as data | | none |
| `identity.carrier`, `body` hashes | admission (re-hash); runner (at load) | submission; every call | `HASH_MISMATCH`; `CARRIER_CHANGED` |
| `identity.remote` pin | runner | every call | open: no fingerprint check of what the service runs |
| `identity.lineage` | admission: the parent exists, `rsi_permitted`, `changes_allowed`, `parent_suites_pass` | submission | `RSI_NOT_PERMITTED`, `CHECK_FAILED` |
| `ports`, `Port.value_schema`, `Port.check_id` | admission (a check on every output, a schema on every `json` port); runner (input names); gate (values against type and schema) | submission; every call | `CHECK_MISSING`, `PORT_MISMATCH`, `CHECK_FAILED` |
| `needs.when` | precondition evaluator in the runner; selection filter | every call | `PRECONDITION_FAILED`, `PRECONDITION_DEFERRED` |
| `needs.external` | admission (every dependency admitted and pinned); runner and permission layer (calls outside the list refused) | submission; every call | `OPERATOR_NOT_ADMITTED`, `PERMISSION_DENIED` |
| `needs.external[].purpose`, package `purpose` | admission (`repin_needs_purpose` and `changes_allowed` on an RSI child); dependency watcher | submission; on upstream release | `RSI_NOT_PERMITTED` |
| `needs.network` | permission layer (named tools); sandbox (everything) | every call | `PERMISSION_DENIED`; blocked by jiuwenbox |
| `needs.dependencies`, `config`, `secrets`, `resources` | isolated verification sandbox; admission (`dependencies_pinned`) | submission; sandboxed calls | `DEPENDENCY_UNPINNED`; unenforced outside a sandbox |
| `changes.effect_class`, `effects` | admission (`effect_class_matches_effects`); permission layer (level, paths); sandbox; librarian (observed against declared) | submission; every call; audit | `EFFECT_CLASS_INCONSISTENT`, `PERMISSION_DENIED`, `audit_violation` Finding. `reversibility` and `scope` are not enforced anywhere yet |
| `changes.state_kind` | admission (fixtures for `reads_external`) | submission | `CHECK_UNTESTED` |
| `guarantees.checks`, every `Check` | admission (runs `admission` and `both` checks on test cases); check runner and gate (`node` and `both` checks) | submission; every call | `CHECK_FAILED`, `CHECK_UNKNOWN` |
| `guarantees.failure_modes` | runner (records the code); gate (folds it); admission (`failure_modes_additive`) | every call; submission | `CAPSULE_RAISED_UNDECLARED`, `FAILURE_MODE_REMOVED` |
| `guarantees.quality` | librarian | audit | `measurement` Finding, Standing move |
| `members`, `wiring` | admission (members admitted, wires type-compatible); composer | submission | open: the composite checks are not specified yet |
| `evolution.rsi`, `may_change` | admission (RSI children: `rsi_permitted`, `changes_allowed`; every Declaration: `rsi_cannot_grant`); freeze (a gate or verifier capsule must allow no RSI) | submission; run start | `RSI_NOT_PERMITTED`, `SCHEMA_NONCONFORMANT` |
| `decl_hash`, `interface_hash`, `code_sha256` | admission computes them; the Binding pins them; runner checks `code_sha256` | submission; every call | `CARRIER_CHANGED` |

**Missing tools or abilities.** Nothing yet checks a remote service's fingerprint, `reversibility` or `scope`, the network use of MCP tools and shell outside a sandbox, or the composite rules. On the Codex runtime nothing but the runner and the sandbox enforces effects. These are the gaps to close before a capsule's promises can be called enforced rather than declared.
