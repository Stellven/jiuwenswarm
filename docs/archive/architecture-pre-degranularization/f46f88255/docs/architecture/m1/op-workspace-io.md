---
type: design
status: draft
version: 2
owner: muk
sources: [../capsule/runner.md, ../capsule/permissions.md, ../../product/prd-m1-full-2026-10-02.txt]
provides: [op.workspace_io, op.workspace_read, op.workspace_write, op.workspace_list]
consumes: []
depends_on: [../capsule/runner.md, ../system/storage.md, ../system/environment.md]
tags: [module, m1, operator]
---

# Ordinary module contract: Workspace operators: one fixed API per operation

> Module API names below retain their op.* namespace for callable interfaces. They are not separately admitted capsule identities; code is pinned through its owning work capability/profile. Screening RSI evaluates helper candidates offline and activation replaces the owner version, preserving runtime ranking checks.

This page owns the workspace operator family, implemented in `cc/workspace.py`. `op.workspace_io` is the family name, not a callable capsule with conditional ports. All three are authenticated broker tool operations through the trusted broker; no model or network.

| Module call | Required inputs | Required output | Effect class |
|---|---|---|---|
| op.workspace_read | path: path | content: file | read_only |
| op.workspace_write | path: path, content: file | written_path: path | idempotent |
| op.workspace_list | directory: path | paths: collection<path> | read_only |

The broker resolves caller Declaration/Binding from the current authenticated dispatch, intersects its declared resource keys with the operator and run authorization, and grants a single-operation capability. The model supplies no caller Declaration, UID, policy, run override or permissions. Readability is authorized input snapshots plus this attempt's workspace; writes are limited to the caller's exact declared output scope. Admitted code/methods, datasets, blueprints, Gate records, hidden fixtures and credentials are never writable. Returned paths are normalized workspace-relative paths.

Resolve without following symlinks, reject absolute paths, traversal and special files, and operate relative to supervisor-held directory descriptors. Check path components at use, not just string-prefix validation. The trusted supervisor executes the filesystem operation and captures evidence. Capsule code does not receive a broader filesystem mount as a substitute. The actual process profile is [environment](../system/environment.md); unavailable confinement fails closed.

Read missing content returns STORE_NOT_FOUND; corrupt bytes return STORE_CORRUPT. Writing already committed identical bytes returns the original path; differing immutable bytes return STORE_CONFLICT. Partial writes use the atomic publication in [storage](../system/storage.md). Listing returns safe paths sorted lexicographically, excluding credentials/hidden files; sorting algorithm is the implementer's choice. No shell is invoked.

The runner owns deadlines, cancellation, duplicate nested IDs and caller remaining budget. Broker capabilities cannot be replayed in another call. Persist write evidence before successful reply. Independently invoke each operation with fake storage and denial cases through [verification](../system/verification.md). Delivery's whole-directory publication uses the trusted storage batch API so several successful file writes do not falsely imply complete delivery.
