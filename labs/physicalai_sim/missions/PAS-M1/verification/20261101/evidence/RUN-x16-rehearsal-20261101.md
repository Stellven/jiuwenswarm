# Verification run: RUN-x16-rehearsal-20261101
Stored in the selected feature's evidence/ (not committed). Observed evidence, not an implementation checklist.

## 1. Execution identity
| Field | Actual value |
| --- | --- |
| TASK ID / run ID / UTC time | PAS-M1-001 / RUN-x16-rehearsal-20261101 / 2026-11-01T23:36:25Z (63.8 s) |
| Level and V IDs | BOUNDARY: V-X1.6 **rehearsal** (T066). Not V-X1.6 itself, which needs a clean clone of an owner commit (T067, plan U-02) |
| Candidate identity | Source: a clean export of the working tree (`git ls-files -co --exclude-standard labs/physicalai_sim`, 589 files, `missions/` excluded) at HEAD `d3054741d2cd` plus uncommitted SIMLAB files |
| Baseline / component revisions | Rebuilt image `sha256:ae0c54951585…` (`docker build --no-cache` from the export's `uv.lock`, 53.8 s); its build identity `d5339f6d04a9…` and lock `85c504fe4dab…` equal the final runner build's |
| PRD, spec, plan and IF versions | Sources r0.4.3; spec r1 (AC-017); plan r2 (B14) |
| Working directory / platform / runtime / dependency versions | Docker build context = the export only; fresh container: no network, read-only root, `/data` empty, `/inputs` read-only |
| Input/fixture/dataset/model/prompt/configuration versions | Declared inputs, exported from the original store by the original build: artifacts/measurements/energy_drift.json, artifacts/observations/energy_total.json, artifacts/observations/qpos_j1.json, artifacts/observations/qpos_j2.json, artifacts/procedure.json, artifacts/scene.xml, experiment.json, manifest.json, recorded-result.json |
| Dependency mode and actual services | Local real |
| Command or reproducible manual procedure | `python tools/fresh_checkout.py --rehearsal --run run-73e46f157e694fc8ac49 --output evidence/x16` (from `labs/physicalai_sim/`, runner up) |

## 2. Per-check observations
| V ID / AC references | Expected outcome / threshold source | Actual outcome | Exit code / counts including skips | Result | Raw artifact location |
| --- | --- | --- | --- | --- | --- |
| V-X1.6 rehearsal (AC-017) | Images rebuild from the lockfile; rerunning the recorded experiment matches the recorded result under its declared rule (bitwise-equal per-step state digests and equal measurements); no file outside the source and the declared inputs is read | Rebuild exit 0; re-authored experiment has the identical experiment ID and manifest SHA-256 ({'experiment_id': True, 'manifest_sha256': True}); fresh run of recorded run `run-73e46f157e694fc8ac49` (TB-06 swing-a): 1 trial, differences [] (equal = True); only the export (build context) and the declared inputs entered the fresh container | exit 0 | REHEARSAL_REPRODUCED (not PASS) | `x16/fresh-checkout.json`, `x16/docker-build.log` |
| V-X1.6 (AC-017) | The same from a clean clone at an owner commit | Not run: no commit contains the SIMLAB code (the owner asked for no commits) | N/A | BLOCKED (owner commit, U-02) | none |

## 3. Scope and validity
- Behavior established: the lockfile-pinned image rebuilds from source alone and reproduces a recorded result bit for bit from declared inputs, with no hidden files; the image ID differs from the original (a different build), while trajectories and measurements do not.
- Behavior not established / failures / blockers: the real X1.6 (clean clone of a commit). Ready to run: after an owner commit, `python tools/fresh_checkout.py --commit <sha> --run <run_id> --output evidence/x16-commit`.
- Reproducibility details: deterministic CPU simulation.
- Reused earlier evidence and comparison basis: none.
- Superseded run IDs / reason: the rehearsal on build `df0cfd615bdd…` (recorded run `run-64eec4d664f540cebe81`, also reproduced) is kept in `x16-build-df0cfd61-superseded/`.
- Follow-up V/work-item references: T067.
- Candidate/input changes after this run: none.
