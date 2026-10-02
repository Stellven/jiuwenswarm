---
type: capsule
tags: [capsule, permissions, jiuwenswarm]
---

# Permissions: how a capsule fits jiuwenswarm

A capsule declares what it will touch. jiuwenswarm already has a permission system that decides, per tool call, whether a call may run. CC's job is to **turn each Declaration into rules that system enforces**, and to say plainly which declarations nothing enforces yet. Read in code at jiuwenswarm `bf0e8af7` (paths under `jiuwenswarm/jiuwenswarm/`, now stale — `ai4r_main_branch` has since moved to `eb4c2901c`, not yet re-checked) and agent-core `e23806c1` (paths under `openjiuwen/`). The agent-core pin, `9e339019`, is now available locally; only the `file_guard` row below has been re-checked against it so far (batch E), the rest of this table's agent-core citations still need their own pass.

## What jiuwenswarm has

| Mechanism | Repo | Where | Keyed by | Decides |
|---|---|---|---|---|
| `PermissionEngine`: ALLOW, ASK or DENY | agent-core | `harness/security/permission_engine/core.py:272` | tool name and arguments | the strictest of three pipelines below |
| tiered tool policy | agent-core | `harness/security/permission_engine/toolguard/tool_policy.py:588` | tool name; argument patterns for shell commands only | allow, ask or deny |
| `file_guard` | agent-core | `openjiuwen/harness/security/permission_engine/fileguard/file_guard.py:595`, confirmed at pin `9e339019` (`FileGuardChecker.evaluate`) | path glob × read, write, execute; the workspace root | allow, ask or deny |
| `net_guard` | agent-core | `harness/security/permission_engine/netguard/net_guard.py:110` | URL or host, for the web-fetch tools only | allow or deny |
| permission rail | agent-core | `harness/rails/security/tool_security_rail.py:186` | every tool call of a DeepAgent | runs the engine; ASK becomes an interrupt for a person |
| three-layer config | jiuwenswarm | `agents/harness/common/rails/permissions/permission_compose.py:237` | global `config.yaml`, user file, session | the rules in force |
| owner scopes | jiuwenswarm | `agents/harness/common/rails/permissions/owner_scopes.py:117` | channel and user | allow or deny before the engine runs |
| jiuwenbox sandbox policy | jiuwenswarm repo, `jiuwenbox/` | `jiuwenbox/src/jiuwenbox/models/policy.py:776` | sandbox | file mounts, Landlock, seccomp, network egress and ingress, environment |
| MCP credentials | jiuwenswarm | `common/mcp_config.py:47`, `server/runtime/mcp/credential.py:318` | MCP server | secret values from an encrypted store |

A call is decided like this: owner scopes first (a hit decides without the engine), then the engine's three pipelines, strictest wins. ALLOW runs the call; DENY returns `PERMISSION_DENIED`; ASK suspends the agent until a person answers. Nothing answers an ASK on an unattended run. The shipped config has permissions `enabled: false`, with `defaults "*": allow`.

## How a Declaration becomes rules

Where the DeepAgent permission rail runs, the runner builds a CC permission layer from the Binding's capsule and supplies it through the host's permission snapshot; a rule set directly on the engine would be overwritten by the next snapshot. The Codex-backed M1 path skips that rail. Separately, the runner enforces its explicit refusal decisions, and the PRD requires a distinct unprivileged process boundary for generated POC execution ([process boundary](process-boundary.md)); neither implies general OS-level confinement.

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

- **Not enforced generally at M1:** `reversibility`, `scope`, the difference between `compensable` and `irreversible`, network use by MCP tools and shell, and secrets outside a sandbox. The generated POC process has a narrower dedicated M1 boundary; broad jiuwenbox mediation is deferred. Remaining observed-versus-declared auditing is future librarian work (`audit_violation`). See issue 54 and the [field map](tools.md#field-validation-and-enforcement-map).
- **MCP tools pass unchecked by default**: they are matched by exact name, and their arguments are never inspected.
- **Bypasses.** An owner-scope allow skips the engine. The silent skills rebuild swaps in an allow-all config. A failed rail build in manual mode installs no rail (fail-open). "Remember" answers persist allows that can loosen a capsule's declared level.
- **Codex runtime skips the host permission rail.** The subscription runtime accepts text only and rejects every tool request; team CLI members are spawned bypassing approvals and sandbox. The runner still applies its explicit allow/refuse contract, but it cannot mediate direct filesystem or socket access by ordinary capsule code. The generated POC process boundary is a separate M1 requirement and remains provisional.
- **ASK needs someone to answer.** A headless runner must supply the host's confirmation hook, or treat ASK as a wait.
- **Per-agent permissions are ignored** by the composer today; permissions are per tool and per user, not per capsule. CC's layer is what makes them per capsule.

## Who builds what

CC supplies the Declaration and the translation above; it does not rebuild the permission engine, `file_guard`, `net_guard` or jiuwenbox. The [CC tooling and field-enforcement map](tools.md#field-validation-and-enforcement-map) lists validation and runtime enforcement separately, including backend-specific gaps.

## Effective M1 deployment contract

The table above describes native reuse behavior, including bypasses; it is not the complete CC enforcement guarantee. The current [environment profile](../system/environment.md) denies direct host filesystem/network/credential access and grants descriptor-scoped broker operations. Unsupported platform or operation fails doctor/refuses launch. The [workspace operators](../m1/op-workspace-io.md) derive effective permissions from the authenticated caller and never trust caller-supplied grants. The runner alone cannot contain arbitrary ordinary code; required process confinement supplies that boundary. There is no fail-open native-rail fallback. Mandatory declared-versus-observed capture is M1; automated librarian drift responses remain later work.
