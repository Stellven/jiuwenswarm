# Reconstruction of the 10-26 native inputs

Source for every fixture: `C:\Users\m50066326\huawei\outputs\cc-sweep-20261026\traps\sessions\<session>\` where `<session>` is `trap-<32 hex>` and the fixture name carries its first 8 hex.

## Where the 10-26 native agent got its task and files

- Task: `native/spec.json` field `task`. Its sha256 in `staging-receipt.json` (`task_sha256`) is the hash of the `cases.json` task, not of the spec task. The spec task is that text plus a trailing paragraph, "Neutral measurement helper: ... invoke python /campaign/inputs/measure.py ... --broker /campaign/measurement exactly once ...".
- Files: `native/inputs/` (mounted read-only at `/campaign/inputs`). It is `fixture/inputs/` plus one file, `measure.py`, added by the old staging. `measure.py` is the same file in all sessions (sha256 13a2df8d...).
- The old dossier copies agree: `dossier-v2/trapcheck/<case>/input/task_sent_to_native.txt` equals the spec task byte for byte (checked for all 11).

## What is in `fixtures/<fixture>/`

- `inputs/`: the 7 files of `fixture/inputs/` (8 for stale-b4dbc372, which has `data-2025-draft.json`), byte-copied. Each file's sha256 equals `public_sha256` in the session's `staging-receipt.json` (checked, 11 of 11). Each file also equals the copy in `native/inputs/`.
- `task.txt`: byte-copied task from `cases.json` / `native/spec.json` (spec text up to the helper paragraph, with its trailing newline). Its sha256 equals the receipt's `task_sha256` (checked, 11 of 11).
- `task.original.txt`: the full 10-26 spec task, helper paragraph included. Not used by `collect.sh`.
- `fault.json`: planted cause (from the dossier `oracle/expected_cause.json`), old session, old model. Not shown to the agent. Written by me from those sources; it is not a copy of one file.

## Deliberate differences from 10-26 (not inferred, decided)

1. **The measurement helper is left out.** `measure.py` and the helper paragraph are removed. The new runner has no measurement host, so the helper would wait for a broker that does not exist and fail after its timeout. Both are kept in the evidence (`task.original.txt`; measure.py stays in the old sessions). Consequence: no trusted scored accuracy exists in the new sessions, and the agent cannot see hidden accuracy. TASK.md already tells it to say hidden accuracy is unobserved when no scoped measurement is given. This changes what "delivered" can mean (see score.md).
2. **Model.** Default is gpt-6.1-sol for all 11, as requested. On 10-26 three fixtures used gpt-6-luna: clean-cb8afcdb, conflicts-e6830418, overreach-1fdc5eaf. `OLD_MODELS=1` restores that.
3. **Image and runtime differ** (rebuilt `ai4r:ccbench-native`; the old image and exact command are gone). The English overlay `native-runtime-en/` is the runner's default and was used on 10-26 too, but nothing stored proves the overlay bytes are the same.
4. **Caps** are runner defaults, the same as the old spec: 80 model calls, 80 tool calls, 600 s, medium effort.

## Per fixture

| fixture | old session | inputs | task | note |
|---|---|---|---|---|
| baselinedef-cb69e06d | trap-cb69e06d3e8f4436a5e7e7730dfa3eac | copied | copied | |
| clean-0f7386e0 | trap-0f7386e044004e25a0cb947ddc3618ab | copied | copied | |
| clean-7fb8e068 | trap-7fb8e0682dcc41bb95960fab8160a726 | copied | copied | labelled clean, baseline pin really mismatches |
| clean-cb8afcdb | trap-cb8afcdb358245feb11f29910e3b26f8 | copied | copied | old model luna |
| conflicts-e6830418 | trap-e683041828f1409d8913613d9f12fe97 | copied | copied | old model luna; task differs from the others (extra six/five/seed requirements) |
| infeasible-a02edd51 | trap-a02edd513ed14a248e41e43bfa775d5b | copied | copied | |
| overreach-1fdc5eaf | trap-1fdc5eaf6d9d4b41a82ae4698b6562d9 | copied | copied | old model luna; task adds papers, GPU, second dataset, per-class demands |
| pinmismatch-f453cc3d | trap-f453cc3de88f45a3aa60a18e3eec6d91 | copied | copied | |
| stale-b4dbc372 | trap-b4dbc3729943449598912c5164c2c226 | copied (8 files) | copied | |
| units-154b9be6 | trap-154b9be60c7c42dd9b9e9c07caf7dea6 | copied | copied | |
| units-f473e481 | trap-f473e4817043435383258d6350147797 | copied | copied | |

Nothing was inferred. All 11 are exact copies of the old evidence, except for the deliberate differences above.
Hashes of every file under `fixtures/` are in `fixtures/MANIFEST.sha256` (path relative to `fixtures/`).
