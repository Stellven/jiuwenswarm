# Baseline: AI4Research-Main after the ai4r_M1plus merge

Commit `beb8780e2` (merge of `ai4r_M1plus` 98c6d01bf into `AI4Research-Main` 7b63ffd59), measured 2026-10-29. Every later change on `ai4r/planned-poc-e2e` must reproduce this.

## Result

**The merge introduced no test failures and moved no pin.**

| Check | Result |
|---|---|
| Unit tests: `tests/unit_tests/{research,research_rsi,scripts,capsule_runtime}` | 3434 passed, 155 failed, 54 errors, 21 skipped |
| The same 209 failing tests on main's pre-merge source (7b63ffd59) | All 209 also fail there. None is new from the merge. |
| `planbench/freeze.py --check` | OK |
| `MANIFEST.sha256`: heldout, contract, haltbench, 10-28 fixtures (111 files) | 0 mismatches |
| `freeze_builder_release.py` (verify only) | "Builder and Benchmark release pins verified" |
| Stage asset pins: `build_research_assets` vs `capsule_catalog.json` | Equal on clean exports of HEAD and of both parents |
| `harbor_suite/assets/*.zip.sha256` | Not checkable here. The zip is an external asset, not in the repo. |

The 209 pre-existing failures fall in three groups:
- RSI script and security tests that need root, cgroups or frozen RSI image paths (`/opt/ai4r-rsi-frozen-*`).
- `PermissionError` in the verify container.
- A few assertion failures that main has too, for example `test_capsule_benchmark_local.py::test_semantic_edge_gate_*` and `test_evaluation_run_evidence_closure.py`.

## How it was run

- **Image:** `ai4r-m1-verify:20261016`, built from `deploy/m1/compose.verify.yaml` (target `verify`). It has no network and the source is mounted read-only.
- **Extra mounts:** the documented override does not mount `deploy/` or `benchmarks/`, and the RSI script tests import both. Added for this run:
  - `deploy/`, `benchmarks/` and `jiuwenswarm/` mounted read-only under `/workspace`.
  - A tmpfs at `/workspace/logs`.
  - `/tmp` raised to 3 GB. At 256 MB, 600+ tests fail with "No space left on device".
- **Command:** `python -m pytest <dirs> -p no:cacheprovider -q -rfE -W ignore::SyntaxWarning`. The `-W` flag is needed because the third-party `pysbd` has an invalid escape, and `pytest.ini` turns warnings into errors, which aborts collection.

## Trap found while measuring: CRLF working tree

This worktree was checked out with Git for Windows' system `core.autocrlf=true`. That left 4,757 files that are LF in git but CRLF on disk, while `git status` still showed clean.
- `research/resources/capsules/verifier_implementation.txt` feeds every stage's checking profile. With CRLF, every `profile_ref` differs from `capsule_catalog.json` (`catalog_pin_mismatch`), and about 1,200 tests fail.
- A `docker build .` from such a tree would bake CRLF into the image and fail the same pin check at runtime.

Check before any test, pin check or image build:

```sh
git ls-files --eol | grep -c "i/lf.*w/crlf"   # must print 0
```

The files were restored by writing each index blob's bytes over the file, only where the sole difference was CRLF. `git -c core.autocrlf=false add -u` afterwards staged nothing.
