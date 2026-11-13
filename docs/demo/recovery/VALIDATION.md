# 20261113 Package Validation v2 prepresentation

All checks ran on Satay on 13 Nov, 08:49–09:20 UTC. No inference, lab or build job was submitted.

## Completed

**Browser rendering.** Google Chrome 156.0.8078.79 ran headless against a local server on 127.0.0.1. All six console views (Result, Engine, Trace, Lessons, Replay, Layers) were captured at 1920×1080 and 1366×768 and visually inspected. Issues found this way and fixed:
- a diagram title overflowed
- bold text inside the Trace cards broke onto its own line
- the header wrapped at 1366 px
- hash links scrolled under the sticky header

Keyboard navigation (1–6, ←/→, N, T, Space) and hash URLs (`#trace` etc.) are implemented.

**Video.**
- In headless Chrome, `demo-final.mp4` (H.264, 1920×1080) played from 0 to 406.03 / 406.03 s at 16× speed with no media error. Under Chrome's virtual clock the `ended` event was not observed, but `currentTime` reached `duration`.
- The poster frame displays.
- The v1 real-time decode check is retained in `MEDIA-CHECK.json`.
- The video and all six raw terminal files are byte-identical to the originals in jiuwenswarm `artifacts/factory/demo-incremental/`.

**Raw replay.** All three `scriptreplay` segments completed with exit code 0 in accelerated mode (`-d 200`).

**Links and safety scan.** Every relative `href`, `src` and `poster` in the console resolves inside the package (checked by `tooling/build_package.py`). The console does not name the excluded run.

**Tests.**

| Suite | Result |
|---|---|
| jiuwenswarm `tests/factory/` (includes the ontology slice-link test and the new agent-model test) | 296 passed |
| siminfeng `bin/` queue tests (`test_jobq.py`, `test_heavy.py`) | 19 passed |
| siminfeng `cc/abrun/test_contention.py` + `bin/test_heavy.py` | 8 passed |
| `context/recovery/test_checkpoint.py` | 2 passed |

**Queue service.**
- `satay-jobq.service` is enabled and active, with Linger=yes.
- Worker PID 40291 has been active since 07:37:42 UTC. NRestarts=1 is the earlier controlled worker interruption.
- Shared queue: 104 succeeded, 18 failed, 47 skipped, 7 cancelled, **0 queued or running**.

**Checkpoint.**
- The new private snapshot `~/backup/factory-checkpoints/checkpoint-20261113T084854-04hpi0hd` was taken with the consistent SQLite backup API from read-only sources.
- Both files match their manifest sha256, and `PRAGMA integrity_check` returned ok for both.
- The snapshot is excluded from this package and stays on internal storage.

**Source restoration.** `RESTORE-CHECK.json` is generated when the package is built. Every bundled repository is restored into an empty scratch directory with `scripts/restore-sources.py`, the pinned commit is checked out, and `git fsck --full` is run. The restored HEADs are compared with `SOURCE-PINS.json`.

**Integrity.**
- `MANIFEST.json` lists the sha256 of every file, and `scripts/verify.py` checks them all.
- The zip's sha256 is beside the zip, and the Danta copy was re-hashed after `sync`. Both are recorded in `HANDOFF.md` in the jiuwenswarm repository (the zip cannot contain its own hash).

**Credential scan.** Every non-binary package file was scanned, with gzip files decompressed. The result is in `SECRET-SCAN.json`. This is a pattern scan, not an exhaustive Git-object audit.

**Reviews.** Four independent reviews were run, and their findings are closed in `REVIEW.md`.

## Limits

- **No human spoken rehearsal.** Script timing is estimated from word counts (about 115 wpm).
- **Rendering was headless.** Check display scaling, full screen and audio on the presentation machine.
- **Reboot recovery is partly tested.** Physical reboot and power loss were not tested. Worker restart under systemd and interrupted-job reconciliation were tested.
- **The slice link** validates names and attaches them to seeded work nodes. It does not verify code edits semantically.
- **Dependencies not bundled:**
  - Qwen weights (contract path and size only)
  - JetPack/CUDA
  - Docker and base and engine images
  - Python environments
  - authenticated Codex

  Bundles keep exact pins but only shallow history. This is not a bare-metal recovery image.

## Versions

| Item | Version |
|---|---|
| Factory Codex transport | pinned `openai-codex-cli-bin` 0.163.0 (not upgraded) |
| Operator CLI | codex-cli 0.167.0 |
| Agent model, historical runs | `gpt-6.1-sol` (see `MODEL-CONFIG.md`) |
| Capsule `engine.expert_streaming` | 2.0.0 in the recorded runs; 2.0.1 with ontology 0.2 current |
| `cc-rsi-v1` | tag object `f8ff8d1f05535ee2f1175ec67a0d0c89139fd63f` → commit `1fe2e572`, unchanged |

The build path already uses native CMake/Ninja with a persistent ccache. No build-speed change or claim was made.

## v3 package (13 Nov, about 15:16 UTC)

- **Built with:** `tooling/build_package.py --base <v2 dir> --out <v3 dir> --rebundle --zip`.
- **Checks passed:** restore check PASS, credential scan with no hits, `verify.py` on 1237 files.
- **Pins:**

  | Repo | Commit |
  |---|---|
  | jiuwenswarm | `6fd0ac45` |
  | siminfeng | `7cab011` |
  | llama-engine | `885eec82` (branch `proof-ask-1`; the earlier refs are kept) |
  | tools | `e897ff4` (unchanged) |

- **Zip:** `20261113 Satay CC Demo and Recovery v3 prepresentation.zip`, 585,265,504 bytes, sha256 `606346f98e0ced0cac5c27ee7198e830122f1dea631be5c5689bd046372c100e`.
- **Copies:**
  - `~/backup`, with the extracted folder beside it.
  - Danta (`/media/muk/Danta`), re-hashed after `sync` with direct I/O. It matches.
- **v1 and v2:** both zips are unchanged in both places.
