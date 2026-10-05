---
id: cap.op-workspace-io
type: module
status: draft
version: 2
sources: [../capsule/runner.md, ../capsule/permissions.md, ../../product/prd-m1-full-2026-10-02.txt]
provides: [op.workspace_io, op.workspace_read, op.workspace_write, op.workspace_list]
consumes: []
depends_on: [../capsule/runner.md, ../system/storage.md, ../system/environment.md]
tags: [module, m1, operator]
level: detail
prd: [2.9, 5.4.3]
---

# Ordinary module contract: Workspace operators: one fixed API per operation

PRD: 2.9, 5.4.3

> Answers: What fixed API does each workspace operation (read, write, list) expose, and under which path rules?

## What it does

> Module API names below retain their op.* namespace for callable interfaces. They are not separately admitted [capsule](../capsule/capsule.md#term-capability-capsule) identities; code is pinned through its work capability/profile. Screening [RSI](../rsi.md#term-rsi) evaluates helper candidates offline and activation replaces the capsule version, preserving runtime ranking [checks](../capsule/fields.md#term-check).

This page is the home of the workspace [operator](README.md#term-operator) [family](../contracts/principles.md#term-message-family), implemented in `cc/workspace.py`. `op.workspace_io` is the family name, not a callable capsule with conditional [ports](../capsule/fields.md#term-port). All three are authenticated broker tool operations through the trusted broker; no model or network.

## Interface

| Module call | Required inputs | Required output | Effect class |
|---|---|---|---|
| op.workspace_read | path: path | content: file | read_only |
| op.workspace_write | path: path, content: file | written_path: path | [idempotent](../contracts/principles.md#term-idempotency) |
| op.workspace_list | directory: path | paths: collection<path> | read_only |

The broker resolves caller [Declaration](../capsule/fields.md#term-declaration)/Binding from the current authenticated dispatch, intersects its declared resource keys with the operator and run authorization, and grants a single-operation capability. The model supplies no caller Declaration, UID, policy, run override or permissions. Readability is authorized input snapshots plus this attempt's workspace; writes are limited to the caller's exact declared output scope. Admitted code/methods, datasets, blueprints, [Gate](../verification.md#term-gate) records, hidden [fixtures](../system/test-surfaces.md#term-fixture) and credentials are never writable. Returned paths are normalized workspace-relative paths.

Resolve without following symlinks, reject absolute paths, traversal and special files, and operate relative to supervisor-held directory descriptors. Check path components at use, not just string-prefix validation. The trusted supervisor executes the filesystem operation and captures evidence. Capsule code does not receive a broader filesystem mount as a substitute. The actual process profile is [environment](../system/environment.md); unavailable confinement fails closed.

Read missing content returns STORE_NOT_FOUND; corrupt bytes return STORE_CORRUPT. Writing already committed identical bytes returns the original path; differing immutable bytes return STORE_CONFLICT. Partial writes use the atomic publication in [storage](../system/storage.md). Listing returns safe paths sorted lexicographically, excluding credentials/hidden files; sorting algorithm is the implementer's choice. No shell is invoked.

The runner is the home of deadlines, cancellation, duplicate nested IDs and caller remaining budget. Broker capabilities cannot be replayed in another call. Persist write evidence before successful reply. Delivery's whole-directory publication uses the trusted storage [batch](../system/storage.md#term-commit-batch) API so several successful file writes do not falsely imply complete delivery.

## Tests

Independently invoke each operation with fake storage and denial cases through [verification](../system/test-surfaces.md).

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.op-workspace-io.AC-01 | US-11 | Reading or writing outside the authorized scope (absolute path, parent traversal, symlink, special file, hidden fixture, credential, store path) is denied and recorded. | BLOCK |
| cap.op-workspace-io.AC-02 | N_node | read of a missing path returns STORE_NOT_FOUND; corrupt bytes return STORE_CORRUPT. | BLOCK |
| cap.op-workspace-io.AC-03 | N_node | write of identical committed bytes returns the original path; different bytes to an immutable path return STORE_CONFLICT. | BLOCK |
| cap.op-workspace-io.AC-04 | N_node | list returns safe paths sorted lexicographically and excludes credential and hidden files. | BLOCK |
| cap.op-workspace-io.AC-05 | N_node | A broker capability is single-operation and cannot be replayed in another call; the model supplies no caller Declaration, policy or run override. | BOUNDARY |
| cap.op-workspace-io.AC-06 | N_node | Write evidence is persisted before the success reply; an interrupted write leaves no partial file. | BOUNDARY |
| cap.op-workspace-io.AC-07 | US-11 | When filesystem confinement is unavailable the operators fail closed. | SYSTEM |
