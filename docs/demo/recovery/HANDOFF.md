# 20261113 Satay Demo Handoff v2 prepresentation

State as of 13 Nov, about 09:20 UTC. Nothing is left running from this continuation: no lab, build or agent job, and no background process.

## Present

1. Extract `20261113 Satay CC Demo and Recovery v2 prepresentation.zip` to internal storage.
2. Open `20261113 Satay CC Demo Console prepresentation.html` in Chrome. Optionally serve it with `python3 -m http.server --bind 127.0.0.1` from the package folder.
3. Press F11 for full screen.
4. Keys:

   | Key | Action |
   |---|---|
   | `1`–`6` | Views |
   | `N` | Speaker notes |
   | `T` | Rehearsal timer |
   | Space | Play/pause on Replay |

5. The script is in `PRESENTATION.md`; Q&A is in `ATTACK QUESTIONS.md`.

**Fallback if the video fails:**
```sh
cd evidence/incremental/recording
for n in 1 2 3; do scriptreplay -t seg$n.timing seg$n.typescript -d 20; done
```

**Presenter task still open:** one spoken rehearsal on the presentation machine, checking display scaling and audio.

## Story and claim boundaries

- **Headline, J-OM13** (historical, 64 tokens):
  - 841.5 → 711.4 ms/token, 15.5% less time per token (+18.3% throughput); 4 runs per headline arm.
  - Image built by factory agent task `bd173c08` (12 Nov, GPT-6.1 Sol), measured in a separately specified experiment.
  - Warm cache, start residency not recorded.
- **Fresh recording**, task `e5b8d4b7` (32 tokens, fill only):
  - Inconclusive (null twice).
  - The operator prescribed the plan, imported the baseline record and reopened the task once. All of this is shown.
- **Excluded:** Run 5.
- **Correctness:** fixed-workload greedy output agreement only.
- **Discovery:** earlier engineering supplied the techniques.

## Repositories

| Repo | Branch | Commit | Notes |
|---|---|---|---|
| jiuwenswarm | `cc-siminfeng` (pushed to `git@github.com:Stellven/jiuwenswarm.git`) | `df8069b1` (packaged pin), pushed | Adds docs/demo/recovery v2, `tooling/build_package.py`, the decision extract, and the `JIUWENSWARM_CODEX_MODEL` controller option plus its test. A later docs-only commit records the backup hashes. |
| siminfeng | `jetson/c1` | `9209e25` | Unchanged |
| tools | `main` | `e897ff4` | Unchanged |
| llama engine | `demo-incremental-4` | `b7910f72` | Refs `recovery/{plain,fill,headline}-20261113` |

**Tags.** No tag moved:
- `cc-rsi-v1` = tag object `f8ff8d1f` → commit `1fe2e572`
- `cc-demo-incremental-v1` = `7e6d8558`

**Capsule versions.**

| Capsule | Version |
|---|---|
| Frozen RSI baseline `cc-rsi-v1` | `engine.expert_streaming` 2.0.0 (used by both recorded runs) |
| Current | 2.0.1 with ontology 0.2. Its only change from the tag is the slice link (`6d10c8c5`; `ccs/` diff +35/−3 in 3 files). |
| factory.builder, factory.lab_client | 1.0.0 |
| factory.methodology_ab | method only, unchanged |

Factory changes, engine candidates and capsule versions are versioned separately. This continuation changed no capsule.

## Effective model configuration

| Use | Model | Path |
|---|---|---|
| Agent | `gpt-6.1-sol` (all 13 factory threads; fresh task at medium effort) | Pinned Codex 0.163.0 transport. Now explicit via `JIUWENSWARM_CODEX_MODEL=gpt-6.1-sol`; unset keeps the default. |
| Advisor | `gpt-6-astra` | `codex exec --sandbox read-only` (0.167.0), outside the factory profile. Prompt and reply are in `reviews/`. |

Details are in `MODEL-CONFIG.md`.

## Backups

| What | Where |
|---|---|
| v1 package, unchanged | `~/backup/20261113 Satay CC Demo and Recovery prepresentation.zip`, sha256 `e89ac589…f076`, and on Danta `/mnt/danta/` (identical) |
| v2 package | `~/backup/20261113 Satay CC Demo and Recovery v2 prepresentation.zip` (580,382,452 bytes, 1069 files) + `.sha256`: sha256 `fed94429cb49c580b65ef87a2a8b7831999cecf8b0c8d2a19209e410b291466f` (rebuilt after the key-handler fix; supersedes `a9318424…`). Identical copy on Danta `/mnt/danta/`, re-hashed after `sync` with direct I/O (bypassing the page cache). The v1 copy on Danta also re-verified. The extracted v2 folder is kept beside the zip in `~/backup`. Source pins: jiuwenswarm `df8069b1`; restore check passed (`RESTORE-CHECK.json`). |
| Private factory checkpoints (internal only, never on Danta) | `~/backup/factory-checkpoints/checkpoint-20261113T073737-_4t_l8fj` and `checkpoint-20261113T084854-04hpi0hd` |
| Pre-continuation backup | `~/backup/demo-session-20261113.tgz` (unchanged) |

## Recovery

- **Queue:** `satay-jobq.service` is enabled and active with Linger=yes. Check it with `systemctl --user status satay-jobq`.
- **After a crash:**
  1. Inspect queue and job state before resubmitting anything.
  2. Reuse the original idempotency keys.
  3. Never start two factories on one database.
- **Restore source:** `python3 scripts/verify.py`, then `python3 scripts/restore-sources.py /new/empty/dir` (result recorded in `RESTORE-CHECK.json`).
- **Restore the database:** only from a private checkpoint, with writers stopped, after saving the live database and its sidecars (`RECOVERY.md`).
- **Not tested:** physical reboot and power loss.

## Budget

See `BUDGET.md`. 0 h of lab time was used, and well under 6 h of wall time is charged. No performance candidate was dispatched:
- The fill screen did show a real bottleneck: 636 ms/token of demand wait.
- But this host's A/A noise (12.8%) set the gate at 25.65%, so one matched comparison could not discriminate.
- The natural next intervention, predictive reads, is what J-OM13 already measured.

## Left untouched

- The `factory-demo` tmux session from the night is still alive. Its recorder and pane processes have been idle since 03:40.
- An SSH login on pts/6 belongs to another operator.

Neither was touched. Close the tmux session yourself if it is yours.

## Remaining actions that need a person

1. A spoken rehearsal of the talk.
2. `sudo umount /mnt/danta` before unplugging the drive.
3. Optional: close the idle `factory-demo` tmux session.

## Next opportunities (for RSI or later tasks; none started)

- Noise-aware replication and gate power.
- Intervention ordering after a positive fill screen.
- Adaptive read policy.
- Effective-config logging in fill-only builds.
- A warm/cold cache protocol for headline claims.
- New capsules for CPU/GPU placement and KV-cache memory.
