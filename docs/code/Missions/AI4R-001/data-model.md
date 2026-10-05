# AI4R-001 Proposed Data Model

Version: 0.1 | Design: [plan.md](plan.md) | Status: draft, not implemented.
This supports the native design; spec.md remains the requirements authority. No legacy migration record is introduced.

## Entities and ownership

| Entity | Proposed fields and constraints | Owner / persistence |
| --- | --- | --- |
| ApplicationProfile | profile_id non-empty opaque ID; data_root absolute canonical path; schema_version=1; runtime_mode=codex_subscription | Bootstrap owns; persist under the new root; create once, never reset on launch |
| AccountConnection | state: runtime_unavailable, signed_out, login_pending, ready, auth_expired, quota_limited, error; generation monotonic integer; account_fingerprint optional opaque profile-local digest; login_attempt_id optional; sanitized model catalog | Account service atomically persists generation and fingerprint under the profile root; never reset the counter on restart. Tokens and raw account identifiers excluded. Pending login instructions live only in memory with bounded lifetime |
| SessionBinding | profile_id, account_generation, session_id, agent_instance_id, thread_id, workspace_path, checkpoint_version | Runtime owns mapping under application session storage; thread_id required after start, never fabricated on failed start |
| Execution | execution_id, binding reference, turn_id optional until accepted, request_id, state: queued, running, waiting_user, completed, canceled, failed, interrupted_unknown | Existing application execution/persistence owner; terminal outcome exactly once per execution |
| PendingInteraction | request_id, execution_id, thread_id, turn_id, item_id, kind, allowed_decisions, expires_at nullable | Backend-owned; match all identities before resolving; secrets excluded |
| ToolReceipt | binding, turn_id, call_id, tool_name, dispatch_state, result_reference | Tool bridge; atomic duplicate suppression; after ambiguous external effect require reconciliation, never claim universal exactly-once execution |
| CapabilityCoverageEntry | C-ID, behavior, source, proposed treatment, gap, fixture, result reference | research.md inventory; measured results linked to TEST_REPORT |

## Relationships

A profile has one account control owner and many session bindings. A binding belongs to one application session/agent and one account generation. Each binding permits one active turn. A team has distinct leader/member bindings connected by Jiuwen's existing coordinator. A pending interaction or tool receipt belongs to one execution, not simply the currently visible frontend session.

## Validation and lifecycle

- Canonical workspace paths must remain inside the selected authorized workspace; reject invalid/traversal paths before tool dispatch.
- Account transitions: signed_out -> login_pending -> ready or signed_out/error; logout invalidates generation before worker shutdown. A stale login completion cannot change the new generation.
- Before admitting work on startup, reconcile managed account/read against the durable account fingerprint. A verified identity match preserves generation; changed or unprovable identity blocks old-thread resume and advances generation before an explicit new binding. Preserve application history. Verify usable stable metadata in G4; never read raw authentication files to invent identity support. Do not expose the fingerprint to the browser or ordinary logs.
- Runs require compatible runtime and ChatGPT account readiness. Quota errors change readiness information without choosing another provider.
- Runtime failure yields interrupted_unknown when completion/side effects cannot be established. Resume reconciles the stored thread; do not create a replacement thread silently.
- New project/session history survives normal restart. Fresh first use is not repeated initialization.
- UI state contains sanitized status and scoped short-lived login instructions only; no usable account token or raw auth-file path is required.
- No legacy profile discovery/import or migration journal; CR-01 explicitly removes that obligation.
