---
type: schema
id: cc.standing.v1
status: proposed
tags: [schema]
---

# Standing · `cc.standing.v1`

The one moving pointer in the library: for each capsule name, which version is current and in what state. It is a log. Each move is a new entry, and the entry with the highest `seq` for a name is the current Standing. Its writer is fixed by `state` (INV-3): admission writes `admitted` when it admits a version, or `admitted_inactive` for an RSI child whose parent has `evolution.rsi: propose`; the librarian (unchecked in M1) writes every other state and every revert, including a person's activation of an `admitted_inactive` version. Entries are keyed by name and `seq`, so two entries cannot claim the same `seq`.

**Rules:** INV-2 (entries are never edited), INV-3.

## Fields

Each entry extends [common](common.md), with `scope.library: true`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `name` | `string` | req | checked |  | The capsule name this pointer is for. Example: `doc.pdf_to_text` |
| `seq` | `integer` | req | checked |  | 1 for a name's first entry, then +1. Gives the entries a total order, which timestamps cannot |
| `prev_hash` | `sha256?` | req | checked |  | The hash of the previous entry for this name; null for the first. The log cannot be rewritten unnoticed |
| `current_hash` | `sha256?` | req | checked |  | The `decl_hash` in use; null when no version is. A revert names an earlier version here, with reason `REVERTED` |
| `verdict_ref` | `Ref(verdict)?` | req | checked |  | The Verdict that admitted `current_hash`; null when `current_hash` is null. The way to a capsule's latest Verdict and tests |
| `state` | `reg(standing_state)` | req | checked |  | See the states below. Only `admitted` versions are offered for selection |
| `reason` | `reg(reason_code)` | req | checked |  | Why it moved. Example: `ADMITTED`, `SUSPECT_DRIFT`, `REVERTED` |
| `evidence` | `list<EvidenceRef>` | opt | unchecked | librarian | The Verdict or Finding behind the move |

**States**, from most to least authority. Only `admitted` is checked in M1.

| State | Meaning |
|---|---|
| `admitted` | current, and offered for selection |
| `admitted_inactive` | admitted, but not offered for selection |
| `deprecated` | not offered for new Bindings; existing Bindings still run |
| `suspect` | evidence against it (e.g. `SUSPECT_DRIFT`); not offered for new Bindings |
| `retired` | withdrawn on evidence (`RETIRED_ON_EVIDENCE`); no new Bindings |
| `revoked` | withdrawn for cause (`REVOKED_SECURITY`); the Binding writer and the runner refuse it |

One `current_hash` per name, so two branches cannot both be live under one name: a live branch takes a new name, with `lineage.relation: specialises`.

## Elsewhere

A Finding moves a capsule only toward less authority, in the order above, and moving up needs a new Verdict; how many failures make a capsule `suspect`: policy `librarian`.

## Reuse

- Write-once KV with prefix reads (agent-core `core/foundation/store/base_kv_store.py:42`, `:93`): as is, with `exclusive_set`.
- `CapabilityProvider.capabilities()` (`symphony/interfaces/capability.py:16`): as is, as a reader.
- `CapabilityDescriptor.available` (`symphony/models/capability.py:69`): not relied on; non-admitted versions are left out instead.
- v2.10b §3.3: the source. `previous[]` (versions it may revert to) became `prev_hash`, a hash chain of entries. Moved to the envelope: `since`, `by`. Not kept: `slot`.
