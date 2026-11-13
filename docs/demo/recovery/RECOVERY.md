# 20261113 Satay Recovery Guide prepresentation

## Restore source without touching live repositories

Run `python3 scripts/verify.py` first. Then `python3 scripts/restore-sources.py /absolute/new/empty/directory`. It initializes each repository, restores its supplied shallow-history boundary, imports the bundled objects/refs, checks out the exact pinned commit and runs git fsck. Use this helper rather than ordinary git clone: shallow bundles require the boundary file. The manifest records original remotes and branches for later resumption. Nested submodules are not automatically fetched. The factory's lab should use the separately restored siminfeng via SIMINFENG_ROOT. Model weights, CUDA/JetPack, Docker runtime/base images and Python dependencies remain installed or separately provisioned dependencies.

Do not start two factories against one database. Following a crash, inspect the queue service and owned running jobs first; reconcile terminal records before deciding whether any job needs resubmission. Reuse the original idempotency key when recovering a submission. Never assume a missing agent session means the underlying build stopped. Never kill a process solely by an old PID.

The included `context/recovery/` documentation describes the implemented service, tests and exact startup limits. A user service cannot guarantee unattended startup before login unless lingering has been enabled. If the validation record flags that requirement, it remains an operator setup step; do not describe reboot recovery as fully automatic.

## Checkpoints and pushes

Repository commits preserve source. Selected evidence archives preserve receipts and recordings. Private SQLite snapshots preserve mutable factory state. They are different backups. Never include Codex auth, SSH keys, environment credentials or session tokens in the transferable package.

Recover a database snapshot only with the controller and its writers stopped, after saving the current database and its sidecars separately. Open the restored snapshot in isolation and verify integrity/task identity before replacing anything. The package deliberately excludes the live database and authentication directories.

## Danta (USB backup drive)

The operator authorized Danta backup writes on 13 Nov.

**The drive:** exFAT, label `Danta`, 57.7 GB. On 13 Nov it was `/dev/sda1`. The operator mounted it at `/mnt/danta` with `uid=1000,gid=1000`. Identify it by label or UUID, not by device name.

**What it holds:** only completed, checksum-verified archives:
- version 1, `20261113 Satay CC Demo and Recovery prepresentation.zip`, which is unchanged
- version 2, `… v2 prepresentation.zip`

Each archive has an adjacent `.sha256`. The procedure is: copy, `sync`, re-hash the copy, then unmount with `sudo umount /mnt/danta`, which needs the operator. HANDOFF.md records the hashes.

**What stays on internal ext4:** active SQLite and Git workspaces, and the private factory checkpoints under `~/backup/factory-checkpoints/`. A private database snapshot is never written to a removable drive.

**What Danta does not replace:** a flash drive on the same powered machine supplements remote pushes and separate backups.
