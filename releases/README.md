# AI4Research release packaging

[AI4Research M1 release notes](AI4Research-M1.md)

The M1 release joins `ai4r_M1` at
`32c77d69d7b64705194dc56d5aac39d02be4924e` with `AI4Research-Main`,
previously `1aaf56ad61d621f8689ddaa91d906532eeedf2cd`. Both histories are
retained, with conflicts resolved in favor of M1. The current M1 refresh also
includes main integration `6bb00afa28cae3c5edc95e7c3217a1a21dbb9890`
(RSI loop delivery, PR #12). The `ai4research-m1` tag and downloadable manifest
identify the current released source snapshot, including release documentation.
The native Python
distribution keeps its existing `workswarm` version `0.2.5.beta1`.

## Verify and run

Download an archive and `SHA256SUMS` into the same directory. On Linux/WSL:

```sh
sha256sum --ignore-missing -c SHA256SUMS
tar -xzf AI4Research-M1.tar.gz
cd AI4Research-M1
export AI4R_LOCAL_WORKSPACE=1
export AI4R_LOCAL_CHAT=1
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml \
  --profile benchmark build ai4r benchmark-runner
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml up -d ai4r
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml logs --tail 100 ai4r
```

For ZIP downloads on Windows, compare `Get-FileHash AI4Research-M1.zip -Algorithm
SHA256` with `SHA256SUMS` before extracting. Build and run in Linux/WSL with
Docker Compose. First builds need network access. No prebuilt images, installed
dependencies or credentials are supplied. Open the complete private bootstrap
URL printed in the app logs at `127.0.0.1:5175` and complete model sign-in.
Preserve existing Docker state/account volumes when upgrading.

See [operations](../deploy/m1/OPERATIONS.md) for authentication, operator
bindings, runtime readiness, platform selection and benchmark execution.

## Reproduce

From a Git checkout with Python 3.11+ and Git:

```sh
python scripts/package_ai4r_release.py --ref <commit-from-release-manifest.json> --output dist/AI4Research-M1
```

Replace `<commit-from-release-manifest.json>` with the manifest's `commit` value.
Use a Git checkout containing that commit. The current release can also be
packaged with `--ref ai4research-m1`. For an earlier downloaded package, use
its own manifest's commit: the M1 tag is refreshed when the published M1 source
is explicitly updated.

The output directory must be new. The packager reads committed Git objects only.
Local environment files, state and previous builds cannot enter the archives.
It also excludes `benchmarks/output/` and benchmark `internal/` directories,
including when packaging an older commit that still tracks these files.

Both archives preserve explicit `.gitattributes` EOL rules, executable bits and
symlinks. This matters because research assets pin actual checkout bytes. The
manifest records the release commit, Git tree, packaged file hashes and any Git
LFS pointers. `SHA256SUMS` covers both archives, release notes and manifest.

The integrated frontend passed its production TypeScript/Vite
build. This source release does not certify a new container build, all benchmark
variants or complete scientific acceptance; existing runtime results remain
scoped to their recorded source/image and conditions.
