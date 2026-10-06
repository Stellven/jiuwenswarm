---
type: capsule
tags: [capsule, permissions, jiuwenswarm]
---

# Permissions: how a capsule fits jiuwenswarm

A capsule declares what it will touch. jiuwenswarm already has a permission system that decides, per tool call, whether a call may run. CC's job is to **turn each Declaration into rules that system enforces**, and to say plainly which declarations nothing enforces yet. Read in code at jiuwenswarm `bf0e8af7` (paths under `jiuwenswarm/jiuwenswarm/`) and agent-core `e23806c1` (paths under `openjiuwen/`; jiuwenswarm pins `9e339019`, which was not available locally).

## What jiuwenswarm has

| Mechanism | Repo | Where | Keyed by | Decides |
|---|---|---|---|---|
| `PermissionEngine`: ALLOW, ASK or DENY | agent-core | `harness/security/permission_engine/core.py:272` | tool name and arguments | the strictest of three pipelines below |
| tiered tool policy | agent-core | `harness/security/permission_engine/toolguard/tool_policy.py:588` | tool name; argument patterns for shell commands only | allow, ask or deny |
| `file_guard` | agent-core | `harness/security/permission_engine/fileguard/file_guard.py:595` | path glob × read, write, execute; the workspace root | allow, ask or deny |
| `net_guard` | agent-core | `harness/security/permission_engine/netguard/net_guard.py:110` | URL or host, for the web-fetch tools only | allow or deny |
| permission rail | agent-core | `harness/rails/security/tool_security_rail.py:186` | every tool call of a DeepAgent | runs the engine; ASK becomes an interrupt for a person |
| three-layer config | jiuwenswarm | `agents/harness/common/rails/permissions/permission_compose.py:237` | global `config.yaml`, user file, session | the rules in force |
| owner scopes | jiuwenswarm | `agents/harness/common/rails/permissions/owner_scopes.py:117` | channel and user | allow or deny before the engine runs |
| jiuwenbox sandbox policy | jiuwenswarm repo, `jiuwenbox/` | `jiuwenbox/src/jiuwenbox/models/policy.py:776` | sandbox | file mounts, Landlock, seccomp, network egress and ingress, environment |
| MCP credentials | jiuwenswarm | `common/mcp_config.py:47`, `server/runtime/mcp/credential.py:318` | MCP server | secret values from an encrypted store |

A call is decided like this: owner scopes first (a hit decides without the engine), then the engine's three pipelines, strictest wins. ALLOW runs the call; DENY returns `PERMISSION_DENIED`; ASK suspends the agent until a person answers. Nothing answers an ASK on an unattended run. The shipped config has permissions `enabled: false`, with `defaults "*": allow`.

## How a Declaration becomes rules

The runner builds a CC permission layer from the Binding's capsule and supplies it through the host's permission snapshot, so the rail applies it on every call. A rule set directly on the engine inside a DeepAgent is overwritten by the next snapshot, so the snapshot is the only safe way in.

| Declared | Becomes | Enforced where |
|---|---|---|
| `changes.effect_class` | the PermissionLevel set by policy `mappings` for the capsule's tool | tool policy for the level; `file_guard` for "inside the workspace"; the runner for "unattended", which the engine does not know |
| `changes.effects[].resource_key` `fs:...` | `file_guard.paths` entries (glob, read, write or execute), plus a registered file-tool spec so the guard reads the capsule's path argument | `file_guard`: the only resource-level check today |
| `needs.network: none` | deny for the capsule's network tools, and `net_guard` default deny | the engine, only for named tools |
| `needs.network: egress, ingress` | the sandbox's egress and ingress lists | jiuwenbox; jiuwenswarm sends only the file policy today, so this needs a small change |
| `needs.external` | allow exactly those capsules' tools, deny the rest (`defaults "*": deny` in the CC layer) | the engine, and the runner, which refuses calls outside the list |
| `needs.secrets` | the sandbox environment, or MCP credential placeholders | jiuwenbox; there is no permission-level secret rule |
| `effect_class` | ToolCard flags, by policy `mappings` | the scheduler, for retries and concurrency; not a permission |

**Trust meets permissions here too.** The runner binds only a capsule whose Standing is `admitted` at a level the call site accepts; permissions then limit what that capsule may do.

## Gaps and conflicts

- **Not enforced anywhere today:** `reversibility`, `scope`, the difference between `compensable` and `irreversible`, network use by MCP tools and shell, and secrets outside a sandbox. These are enforced only in jiuwenbox, and otherwise checked after the fact by comparing observed effects with declared ones (librarian, `audit_violation`).
- **MCP tools pass unchecked by default**: they are matched by exact name, and their arguments are never inspected.
- **Bypasses.** An owner-scope allow skips the engine. The silent skills rebuild swaps in an allow-all config. A failed rail build in manual mode installs no rail (fail-open). "Remember" answers persist allows that can loosen a capsule's declared level.
- **Codex runtimes skip the whole system.** The subscription runtime accepts text only and rejects every tool request; team CLI members are spawned bypassing approvals and sandbox. So for M1 on Codex, capsule effects are enforced only by the runner and the sandbox, never by the rail.
- **ASK needs someone to answer.** A headless runner must supply the host's confirmation hook, or treat ASK as a wait.
- **Per-agent permissions are ignored** by the composer today; permissions are per tool and per user, not per capsule. CC's layer is what makes them per capsule.

## Who builds what

CC supplies the Declaration and the translation above; it does not rebuild the permission engine, `file_guard`, `net_guard` or jiuwenbox. The tools that do the translation and checking are listed in [tools](tools.md#which-tool-checks-each-field).
