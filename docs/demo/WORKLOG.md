# Incremental CC demo — worklog (append as we go; commit + push often)
Push: HTTPS origin has no creds; use `git push git@github.com:Stellven/jiuwenswarm.git cc-siminfeng` (gh logged in as Muxite, ssh).

- 2026-11-13 00:5x  Satay crashed ~00:47 (no clean shutdown, no pstore/reset reason; likely power/hard freeze). Recovered uncommitted WIP, committed 6ad26118 and pushed.
- Existing tooling: factory story --demo, demo_record.sh (tmux+script), demo_cut.py (compress), demo_panes.py, docs/demo/cards.py + engine-diagram.svg, tasks/demo-incremental.json.
- 00:5x resumed task factory-3d24382b (fill built, image f7742a19) via RESUME_TASK in a new recording segment (3rd attempt; attempt1 DISK_SPACE_LOW, attempt2 crashed at host reboot)
- 01:1x attempt 3 (resume) failed: NEW_SESSION_REQUIRED + wall-clock budget counted downtime. Started a fresh task on branch demo-incremental-3 (wall clock 6000 s). Attempt-2 raw recording kept (fill integrate+build, image f7742a19) as a fallback segment.
- Facts: qwen36-quick-v1 exists (32 tok, own reference frozen 22:04 on plain image a9a0c71c); 64-token qwen36-bare-greedy-v1 (Run 4 / J-OM13 workload) is a different workload — never mixed.
