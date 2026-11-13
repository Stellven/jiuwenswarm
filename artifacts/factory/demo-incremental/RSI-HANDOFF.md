# RSI handoff — incremental demo

**Baseline capsule (unchanged):** tag `cc-rsi-v1` (`f8ff8d1f`), `engine.expert_streaming` 2.0.0 and the shared CCs. `git diff cc-rsi-v1..cc-demo-incremental-v1 -- jiuwenswarm/factory/ccs` is **empty**: no capsule or method file changed, the keep gate (ABBA, `component.yaml` acceptance) was not lowered, and no preliminary evidence was sent through it. `RSI-START-HERE.md` is untouched; start there.

**Same environment:** the installed Satay environment, shared model/image assets and the serialized jobq queue (needs a live `bin/jobq worker`). RSI candidates use separate source/task identities (a new task id and branch such as `rsi-*`; do not reuse `demo-incremental-4`). No Spark setup.

**Hand-over inputs:** baseline capsule (above) · plain source `cf34d3113` / image `factory/llamacpp:bare-cf34d311` (`sha256:a9a0c71c…`, receipt `operator-bare-build:346fe01b`, import with `jiuwenswarm factory baseline-import <task>`) · contract `qwen36-quick-v1` (frozen, ref `cad62aa9`) and the 64-token `qwen36-bare-greedy-v1` (ref `7a154179`) · evidence: `RESULTS.md`, `results.json`, task `factory-e5b8d4b7…` in `~/.jiuwenswarm-factory`.

**Host changes made after the tag for this demo (tag `cc-demo-incremental-v1`, none touch the capsule):**
- crash-safe resume (`controller.py`): wall-clock budget counts running time only; a resumed run opens a new agent session with full context (the old one is gone after a reboot);
- operator commands `factory baseline-import`, `factory note`; an operator note reopens an inconclusive/partial task (accept/reject stay final);
- `story --demo` presentation view, `demo_record.sh` (starts/validates the jobq worker), `demo_cut.py`, tests (`tests/factory`, 292+ pass).

**Observations worth improving (for RSI):** the screening/ABBA flow had no way to admit an existing baseline build until the import command (the agent correctly refused to rebuild unchanged source); a 1-round ABBA on this host is too noisy to clear its gate (A/A 4–13%), so keep decisions need ≥3 rounds or a quieter host; the fill-only build lacks patch 08/09 logging so contract-level engagement checks read 0/2 — engagement should be judged from the fill counters; agent calls showed several `INVALID_INPUT` retries on builder/evidence calls.

**Not established:** any confirmed gain for demand fill alone on the quick contract; predictive reads under the factory (only J-OM13/Run 4 evidence); behaviour on workloads other than these two prompts.
