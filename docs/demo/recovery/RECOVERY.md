# 20261113 Satay Recovery Guide prepresentation

## Restore source without touching live repositories

Run `python3 scripts/verify.py` first. Then `python3 scripts/restore-sources.py /absolute/new/empty/directory`. It initializes each repository, restores its supplied shallow-history boundary, imports the bundled objects/refs, checks out the exact pinned commit and runs git fsck. Use this helper rather than ordinary git clone: shallow bundles require the boundary file. The manifest records original remotes and branches for later resumption. Nested submodules are not automatically fetched. The factory's lab should use the separately restored siminfeng via SIMINFENG_ROOT. Model weights, CUDA/JetPack, Docker runtime/base images and Python dependencies remain installed or separately provisioned dependencies.

Do not start two factories against one database. Following a crash, inspect the queue service and owned running jobs first; reconcile terminal records before deciding whether any job needs resubmission. Reuse the original idempotency key when recovering a submission. Never assume a missing agent session means the underlying build stopped. Never kill a process solely by an old PID.

The included `context/recovery/` documentation describes the implemented service, tests and exact startup limits. A user service cannot guarantee unattended startup before login unless lingering has been enabled. If the validation record flags that requirement, it remains an operator setup step; do not describe reboot recovery as fully automatic.

## Checkpoints and pushes

Repository commits preserve source. Selected evidence archives preserve receipts and recordings. Private SQLite snapshots preserve mutable factory state. They are different backups. Never include Codex auth, SSH keys, environment credentials or session tokens in the transferable package.

Recover a database snapshot only with the controller and its writers stopped, after saving the current database and its sidecars separately. Open the restored snapshot in isolation and verify integrity/task identity before replacing anything. The package deliberately excludes the live database and authentication directories.

## Danta later

No operation in this package mounts or writes Danta. When explicitly asked later, identify it by filesystem UUID/label and available capacity; do not assume /dev/sda1. Copy a completed, checksum-verified archive to it, sync it, verify the copied archive hash and safely unmount. Keep active SQLite and Git workspaces on internal ext4. A flash drive on the same powered machine supplements, rather than replaces, remote pushes and separate backups.
