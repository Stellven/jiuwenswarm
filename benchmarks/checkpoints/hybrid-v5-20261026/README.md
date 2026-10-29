# Hybrid v5 checkpoint — 26 October 2026

This preserves the current integrated AI4R router, not a second app or branch.
The running service was not restarted or changed during preservation.

v5 had the highest **raw answer correctness** among the measured hybrid
versions: 21/24, with 198,698 reported tokens (12.46% below all ChatGPT).
Its component gate advanced 11 correct answers; v4 advanced 14. Thus v5 was
not best on every metric. This is a public MR01 development component result,
not a complete AI4R workflow acceptance result.

## Saved locally on D:

- `source-overlay.zip`: exact copies of 42 modified/new source, contract,
  frontend, benchmark, focused-check and report files.
- `source-manifest.json`: base Git commit, each file's SHA-256 and size, archive
  hash, and deleted paths (none in this checkpoint).
- `deployment.json`: frozen v5 policy, measured image IDs and Spark image tags.
- [Benchmark report](../../reports/2026-10-26-hybrid-router/benchmark-report.html).

The archive is about 1.2 MB. It excludes model weights, account credentials,
reviewer answer files and full Docker image exports. It includes the illustrated
report as it existed at preservation time. The main worktree and Git staging
area were left intact. No remote Git push was performed.

## Saved on Spark

Directory: `/home/user2/ai4r-data/checkpoints/hybrid-v5-20261026`

- `deployment.json`: image IDs and exact routing policy.
- `images.json`: Compose image override for the checkpoint.
- App image tag: `ai4r-spark:hybrid-v5-20261026`.
- Runner image tag: `ai4r-benchmark-runner:hybrid-v5-20261026`.
- Original receipts remain under
  `/home/user2/ai4r-data/benchmarks/hybrid-operations-001`.

Docker tags reference the existing image layers and do not duplicate their
large storage. Keep these images during future image pruning. The tags are on
this Spark host, not a registry backup; deleting the images or losing the host
would remove that deployment copy. The D-drive source snapshot remains separate.

## Restore source without overwriting ongoing work

Run these only when a restoration is desired. Choose an unused D-drive worktree
path; this is a recovery workspace, not another running app.

```powershell
cd D:\research\ai_for_research\runs\jiuwenswarm
$checkpoint = Join-Path $PWD 'benchmarks\checkpoints\hybrid-v5-20261026'
$manifest = Get-Content (Join-Path $checkpoint 'source-manifest.json') -Raw | ConvertFrom-Json
$archive = Join-Path $checkpoint 'source-overlay.zip'
if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne $manifest.archive_sha256) {
    throw 'Checkpoint archive hash mismatch'
}
$restore = 'D:\research\ai4r-hybrid-v5-restore'
if (Test-Path -LiteralPath $restore) { throw 'Choose an unused recovery path' }
git worktree add --detach $restore $manifest.base_commit
if ($LASTEXITCODE -ne 0) { throw 'Could not create recovery worktree' }
Expand-Archive -LiteralPath $archive -DestinationPath $restore -Force
foreach ($file in $manifest.files) {
    if ((Get-FileHash (Join-Path $restore $file.path) -Algorithm SHA256).Hash.ToLower() -ne $file.sha256) {
        throw "Restored file mismatch: $($file.path)"
    }
}
```

The base commit is `0fa35ee38e636e594f9252bc7fcb98e79d45d1b0`.
The overlay is a complete copy of changed/new files, not a stand-alone Git
repository. Restoration needs that base commit. Runtime data, model services
and ChatGPT sign-in remain separately managed deployment resources.

## Restore the saved app image on Spark

This deliberately replaces the running app container; do it only when ready to
interrupt active app requests. It keeps the existing Compose volumes/settings,
does not rebuild images, and does not restart shared model services.

```bash
cd /home/user2/ai4r-data/deployment
test "$(docker image inspect ai4r-spark:hybrid-v5-20261026 --format '{{.Id}}')" = \
  'sha256:dcb5f77624f9f57d3eb595339a0eb2a0b647d1e58e3e63bf93aa64a83af58f3e' || exit 1
docker compose -p ai4r-spark \
  -f /home/user2/ai4r-data/deployment/compose.json \
  -f /home/user2/ai4r-data/checkpoints/hybrid-v5-20261026/images.json \
  up -d --no-build --no-deps ai4r
```

The image restore command was **not executed** while saving this checkpoint.
It relies on the existing deployment configuration and persistent data still
being compatible; this snapshot is not a backup of mutable application state.
