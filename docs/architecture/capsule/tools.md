---
type: capsule
tags: [capsule]
---

# Tools

CC is a schema; tools do the work. Each tool reads the [Declaration](../schemas/declaration.md) or records about a capsule, and writes one kind of record. Tools are control code, never capsules. Which fields M1 checks is on [stages](stages.md).

**M1** says whether M1 (the PRD's first milestone) needs the tool: **needed** when M1 depends on the checked fields it reads or writes, **not needed** when the tool exists to read unchecked fields. For each not-needed tool, the table names the unchecked fields it unlocks.

**Builds on** names an existing jiuwenswarm or openJiuwen piece the tool could reuse, found in the code. jiuwenswarm paths are under `jiuwenswarm/jiuwenswarm/` at commit `aae2046c4`. agent-core paths are under `openjiuwen/`; they were read in a clone at `e23806c1`, while jiuwenswarm pins `9e339019`, so they carry no line numbers. "None found" means we found nothing to reuse.

## The tools

| Tool | Reads | Writes | M1 | Builds on |
|---|---|---|---|---|
| **Author kit** | a draft Declaration, its files, its tests, the [policy](../schemas/policy.md) | nothing stored: a report for the author | needed | none found |
| **Admission** | a [Candidate](../schemas/candidate.md), the policy | [Verdict](../schemas/verdict.md), [Standing](../schemas/standing.md), test cases and test suites, Artifacts for test inputs and fixtures, stored files | needed | none found |
| **Runner** | the [Binding](../schemas/binding.md), the Declaration, the code by hash | [Artifact](../schemas/artifact.md), [Observation](../schemas/observation.md) | needed | Swarmflow's `agent()` (agent-core `agent_teams/workflow/engine/primitives.py`); on the DeepAgent (harness) path only, the permission rail (below) and `RailManager` (`agents/harness/common/plugins/rail_manager.py:52`), which registers custom rails (hooks) on the DeepAgent |
| **Check runner and gate** | [checks](../schemas/checks.md), Artifacts, Observations, the Binding, the policy | [Verification](../schemas/verification-record.md); later, Findings of kind `fit_failure` and `use_outcome` (unchecked) | needed | agent-core Symphony `Evaluator` protocol (`symphony/evaluation/base.py`) for check runners |
| **Library store** | everything admission and the runner write | records keyed by id, code keyed by sha256 | needed | agent-core `BaseKVStore` (`exclusive_set`, `get_by_prefix`) and its object store |
| **Lineage index** | `identity.lineage` of every admitted version | an index from each `decl_hash` to its parent and children | not needed. Unlocks tracking and merge: `identity.lineage` (`parent_hash`, `relation`, `co_parent_hashes`) | none found |
| **Librarian** | Standing, Observations, Verifications, Findings | Standing changes, [Findings](../schemas/finding.md), including kind `measurement` | not needed. Unlocks `guarantees.quality`, every Finding field, Observation `effects_observed`, Standing `evidence` | none found |
| **RSI submitter** | reports from an RSI engine, the parent's Declaration and Verdict | Candidates with `submitted_by.kind: rsi` and `lineage.parent_hash` | not needed; RSI is built on a separate branch that shares the schema. Unlocks `identity.lineage`, `guarantees.failure_modes`, Candidate `builder_evidence` and `test_aids`, test suite `inherited_from_hash`, Artifact `issues`, Binding `overlays`, Observation `trajectory_ref` | jiuwenswarm RSI service (`agents/harness/common/rsi/`); agent-core `rsi/` |
| **Selection index** | name, summary, ports, effect class, Standing | an index of admitted capsules for search and for matching by port type; Findings of kind `gap` when no capsule fits | not needed. Unlocks `identity.tags`, `Predicate.state_source` | jiuwenswarm `SkillTaxonomyRuntime` (`symphony/skill_retrieval/runtime.py:30`) over agent-core `AgenticSkillRetrievalToolkit`; agent-core Symphony `CapabilityProvider` (`symphony/interfaces/capability.py`) |
| **Cost meter** | Observations | token and money cost per call, for Binding budgets | not needed; the first epoch budgets time only. Unlocks Observation `cost.tokens`, `cost.money`, Binding `budget.tokens`, `budget.money` | GenAI span attributes (`gen_ai_semconv.py:53-90`) |
| **Importer for outside sources** | a skill, tool, MCP server or A2A agent from a hub, a repo or a local folder | draft Declarations, checks and test cases, and Candidates with `submitted_by.kind: importer` | not needed. Unlocks Candidate `source`, `identity.namespace`, `identity.license`, `needs.dependencies`, `needs.config`; for MCP servers and A2A agents, `identity.remote` | `SkillManager` install handlers (`server/runtime/skill/skill_manager.py`); the MCP registry (`server/runtime/mcp/registry.py`); agent-core MCP clients (`core/foundation/tool/mcp/client/`) |
| **Isolated verification sandbox** | a Candidate from outside, its `needs.dependencies`, `needs.config`, `needs.secrets` and `needs.resources`, the policy | test results for admission, Verdict `environment`, the effects observed | not needed. Unlocks `needs.dependencies`, `needs.config`, `needs.secrets`, `needs.resources`, Verdict `environment` | jiuwenbox (`jiuwenbox/` at the jiuwenswarm repository root) |
| **Store or registry** | admitted capsules, their Verdicts, Candidate `source` | published capsules with their Declarations | not needed. Unlocks Candidate `source` (with `attestation`), `identity.namespace`, `identity.owner`, `identity.tags`, `identity.license` | openJiuwen Agentic Hub (`openjiuwen/skillhub`); jiuwenswarm `HubClient` (`server/runtime/marketplace/hub_client.py:150`) |
| **Composer** | Observations of capsules that run in sequence and pass | a Candidate for a `composite` capsule | not needed. Unlocks `members`, `structure`, `wiring`, `identity.lineage.co_parent_hashes`; see [composition](composition.md) | none found |
| **Remover** | Standing, each effect's `undo` | a Standing change (`retired` or `revoked`), written through the librarian | not needed. Unlocks uninstall. `undo` is text, applied by a person or a later tool | none found |

Needed tools also read unchecked fields once they exist. Admission reads the certification fields: Candidate `requested_level`, test case `negative_control`, test suite `access`, `visibility`, Verdict `evidence_requests`. The runner and gate read the retry and fallback fields: `idempotency_key`, `guarantees.failure_modes`. Every tool may write `trace` for tracing.

## How the M1 tools work

**Author kit.** Authors run it before they submit. It checks a draft Declaration against the schema and the policy's `required` section. It hashes every file, computes `decl_hash` and `interface_hash`, and runs the capsule's admission checks on its test cases. It should share admission's shape and hash code, so that the two agree.

**Admission.** It decides whether a capsule enters the library. In order, it:

1. checks the Declaration's shape and the policy epoch;
2. hashes every file again, and refuses the capsule if a hash differs;
3. applies the policy `rules`, among them: effects agree with `effect_class`, every output has a check, every admission check has a test case, every capsule in `needs.external` is admitted, and a pinned one names an admitted `decl_hash`;
4. stores the files by hash, and writes the test cases and the test suite;
5. runs the tests through the runner, as Observations with `caller: admission`;
6. writes the Verdict and, if admitted, a Standing entry.

Every refusal carries a reason code, such as `HASH_MISMATCH`.

**Runner.** Every capsule call goes through it. It checks the code against the Binding's hashes, checks preconditions, calls the capsule by its kind, stores each output as an Artifact and writes an Observation. A call with no Observation went around the runner.

**Check runner and gate.** Check runners run the checks on an output: `deterministic` and `reference` checks with no model first, then `judged` checks. The gate adds its own fixed checks, `check.call_ok.v1` and `check.within_budget.v1`, folds all results into `pass`, `fail` or `blocked`, as policy `gates` defines, and writes one Verification for each `dispatch` call.

## For imported capabilities

- The importer drafts the Declaration, the checks and the test cases. A person or the author kit completes them before submission, because admission needs at least one check and a test case for each admission check.
- One MCP server becomes one capsule per tool it exposes. A2A agents come in the same way, as `a2a` capsules pinned by endpoint and version.
- Every capsule named in `needs.external` is imported and admitted first.
- A receiving system re-admits every capsule under its own policy epoch. Another store's Verdict is evidence, not admission.

## What the existing pieces give

- **Permission layer.** `JiuwenSwarmPermissionInterruptRail` (`agents/harness/common/rails/permissions/permission_interrupt_rail.py:44`) and agent-core `PermissionEngine` (`harness/security/permission_engine/core.py`) decide whether a tool call may run. The runner can ask them for a capsule's declared `effect_class` and `needs.network`.
- **Codex runtime.** Under the Codex subscription runtime the team uses now (set by `codex_start.py:21`; the code default is `harness`), only user text is accepted: skills, MCP, plugins, agent templates and team mode are refused (`server/runtime/agent_adapter/interface_codex.py:39-42`), so the runner cannot rely on `RailManager` or the permission rail there.
- **Skill loading.** `SkillManager` already installs skills from online search, ClawHub, SkillNet, team hubs and local folders. An importer would wrap these and add the Declaration and admission. It cannot trust the installed copy's version: a skill's files can change under the same version (`touch_version_metadata`, `server/runtime/skill/archive_store.py:267`, recomputes the checksum and keeps the version). So the hash is taken on a read-only copy.
- **Checksums.** The hub downloader already refuses a package whose SHA-256 differs (`server/runtime/marketplace/hub_package_downloader.py:130`). That proves the download, not the tested code; admission still hashes every file.
- **Sandbox.** jiuwenbox runs tools and code in a Linux sandbox (bubblewrap, Landlock, seccomp, optional network isolation) and keeps audit logs. jiuwenswarm can already send tool execution to it. It would install `needs.dependencies`, inject `needs.secrets` and enforce `needs.resources`.
- **Store.** The Agentic Hub publishes and versions skills, with a ClawHub-compatible API. It stores packages, not Declarations or Verdicts.
