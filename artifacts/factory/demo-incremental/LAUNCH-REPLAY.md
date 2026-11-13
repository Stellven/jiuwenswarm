# Launch / replay — incremental CC demo

**Watch (no Satay needed):** `artifacts/factory/demo-incremental/demo-final.mp4` (6.8 min; sha256 in `SHA256SUMS`).
Captions name the phase; the footer shows real elapsed run time; waits are compressed and marked "⏩ … compressed".

**Replay the raw terminal sessions** (uncompressed, real timing; `-d 20` = 20× speed):
```sh
cd artifacts/factory/demo-incremental/recording
for n in 1 2 3; do scriptreplay -t seg$n.timing seg$n.typescript -d 20; done
```

**Re-cut the video** (presentation tooling only; needs pyte + Pillow in a venv, and an ffmpeg binary):
```sh
python docs/demo/cards_pil.py OUT/cards
python -m jiuwenswarm.factory.demo_cut --typescript seg1.typescript --timing seg1.timing --out seg1.mp4 \
   --target 150 --card OUT/cards/intro.png:14 --caption "0:caption text" ...   # see demo_cut.py --help
```

**Re-run the live recording on Satay** (agent-driven; ~1 h of real time, shared GPU queue):
```sh
cd ~/projects/jiuwenswarm; export FACTORY_HOME=~/.jiuwenswarm-factory
jiuwenswarm/factory/demo_record.sh            # starts the jobq worker if absent, tmux layout, raw recording
RESUME_TASK=<task id> jiuwenswarm/factory/demo_record.sh   # continue after a crash/reboot (new agent session)
jiuwenswarm factory baseline-import <task>    # operator: reuse the existing plain build (no rebuild)
jiuwenswarm factory note <task> "text"        # operator instruction, reopens an inconclusive task
```
Prerequisites: a running `siminfeng/bin/jobq worker` (nothing starts it after a reboot; `demo_record.sh` now does), Codex login, ~17 GB free disk.
Results and identities: `RESULTS.md` / `results.json`.
