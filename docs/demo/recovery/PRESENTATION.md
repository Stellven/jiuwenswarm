# 20261113 Satay Ten Minute Demo prepresentation

**Audience:** engineering supervisors and colleagues who know agents but not this engine or factory.

**Goal:** they leave knowing three things: what a capability capsule (CC) contributes, where it changes the engine, and why packaging more engineering knowledge this way is worth continuing.

**Slot:** a ten-minute talk inside a fifteen-minute slot, leaving five minutes for questions (see `ATTACK QUESTIONS.md`).

## Setup (before the slot)

1. Extract the package to internal storage.
2. Open `20261113 Satay CC Demo Console prepresentation.html` in Chrome, either directly as a file or through `python3 -m http.server --bind 127.0.0.1` from the package folder.
3. Press F11 for full screen.
4. Check that the Replay view shows the poster frame and that the audio/visual output plays a few seconds. Then return to Result.
5. Keys:

   | Key | Action |
   |---|---|
   | `1`–`6` | Jump to a view |
   | `←` / `→` | Previous / next view |
   | `N` | Speaker notes |
   | `T` | Rehearsal timer |
   | Space | Play/pause on Replay |

6. Fallback if the video won't play: open `REPLAY.md` and run the `scriptreplay` commands in a terminal.

## Script (talk 3:14 + video 6:46 = 10:00)

| Time | View | Say |
|---|---|---|
| 0:00–0:35 | 1 Result | "A capability capsule is packaged engineering knowledge for an agent: which change to try, its dependencies, how to check it and when to stop. On a 22-gigabyte MoE model running on an 8-gigabyte Jetson, an agent used the capsule to build an engine. A separate matched experiment measured it at 15.5% less decode time, with identical output. The video later is a different task, and it was inconclusive." |
| 0:35–1:25 | 2 Engine | "Each token, the router picks a few experts. Their weights live in a memory-mapped file almost three times bigger than memory, and they are computed on the CPU. In stock llama.cpp, compute threads stall on page faults inside the matmul. The capsule adds a hook just before that matmul. Demand fill reads the missing ranges with 16 parallel workers, then compute continues. The headline version also predicts the next layer's experts. Nothing moves to the GPU; we change how and when weights are read." |
| 1:25–2:15 | 3 Trace | "This is one recorded task, and who decided what. Dashed boxes are the human operator: the plan, fill first with prerequisites off. Amber boxes are capsule rules: which patches go together, how to check that fill really ran, the noise gate and the revert order. The agent built once and confirmed fill read 6.27 GB. It stopped when it couldn't verify the baseline. ABBA means alternating baseline and change. The result was faster but inside the noise, so null, and it reverted. The operator reopened it once for a longer run. Null again, and reported inconclusive." |
| 2:15–2:35 | 4 Lessons | "Two lessons. First, present in source is not switched on: the prerequisites made decode slower when enabled, so the capsule keeps them dormant. Second, a compiler can spoil a measurement, so builds and lab runs now share one queue." |
| 2:35–9:21 | 5 Replay | Press Space. Optional brief cues: capsule reads, "build once", the 6.27 GB screen, the stop and import, "gate null", the revert, the reopen, the final report. |
| 9:21–10:00 | 1 Result | "So the technique came from earlier engineering. What's new is that it's packaged: an agent can apply it inside a plan, build from source, measure against a fixed contract and leave a traceable decision, including stopping and reverting. The frozen capsule, cc-rsi-v1, is the baseline for the next phase, where agents try to improve the capsule itself. None of that has run yet. Thank you." |

Word counts: about 80, 95, 105, 45 and 75, which is 105–145 words per minute. Timing is estimated from script length. **A human spoken rehearsal is still the presenter's task.** The screen timer is a rehearsal aid, not a benchmark timer.

## Evidence boundaries (never cross these)

- **J-OM13 (headline):**
  - historical, recorded, 64-token `qwen36-bare-greedy-v1`
  - base 841.4975 vs fill + predictive reads 711.425 ms/token; four runs per headline arm, 8 of 12 runs
  - 15.457% less time per token, 18.283% higher throughput; gate improved (threshold 8.01%)
  - output byte-identical in all 12 runs
  - the third, thread-count arm is in the report but not in the headline
- **Fresh recording:**
  - 32-token fill-only task `factory-e5b8d4b7`
  - inconclusive; both gates null
  - Never quote its fastest run. Never combine its ratios with J-OM13's.
  - It did not produce the headline.
- **Excluded:** the shelved run is not shown or discussed.
- **Correctness:** byte-identical greedy output on the fixed workload, not general model accuracy.
- **Discovery:** prior human and agent engineering supplied the techniques. The factory demonstrates applying packaged knowledge, not autonomous invention.
- **Provenance of the headline image:** factory agent task `bd173c08` (12 Nov, GPT-6.1 Sol) integrated the components one at a time and kept fill and predictive reads on their gates. J-OM13 was a separately specified 12-run experiment on that image. It ran on a warm page cache with start residency not recorded, and before contention recording existed.
- **Attribution in the fresh task:** the operator's objective prescribed fill first, prerequisites off, one build/screen/ABBA and no tuning. The capsules supplied the patches and dependencies, the engagement checks, the gate and the revert order. The operator imported the baseline record and reopened the finished task for one confirmation.
- **Raw Codex:** no controlled comparison against a raw coding agent exists. Don't claim superiority.
- **Ontology slice link:**
  - added 13 Nov 07:36 (`6d10c8c5`, capsule 2.0.1), after the recording, which used capsule 2.0.0
  - Present it as new traceability, not as something that steered the recorded run.

## The two engineering details

These are in Console view 4. Full sources are in `context/engineering/ENGINEERING-DETAILS.md`.

1. **Source dependency is not runtime enablement.**
   - In agent task `bd173c08`, enabling the prerequisites made decode slower: `mmap_advice` 894 → 1825 ms/token, `router_prefetch` 928 → 1494.
   - Fill needs patch 02's hook, so the agent kept both components in source with their switches off (`keep_dormant`, rev 6 and rev 10). Fill (+11%) and predictive reads (+12.5%) then passed their gates.
   - In the fresh task, when fill was rejected, the agent reverted all three in reverse order (rev 9).
2. **Compilation can spoil a measurement.**
   - On 10 Nov a lab run was unscored because a C++ build ran at the same time; the run watchdog's swap-rate limit also tripped.
   - GPU and build jobs are exclusive in one queue (siminfeng `585cb23`). Compiles are routed into it, and contended runs are unscored (`e410103`). Factory jobs use the shared queue (`5b2830fb`).
   - In the fresh confirmation, all 12 runs record `host_contention false`.
