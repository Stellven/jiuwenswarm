# 20261113 Independent Demo Review v2 prepresentation

On 13 Nov, after a first v2 draft, four independent reviews ran in parallel. Each reviewer was given only the package and the primary sources, not the author's conclusions:
- **Fact-check:** Claude subagent, read-only. Checked every number, hash, path and commit against primary sources and repositories.
- **Adversarial:** Claude subagent, read-only, acting as a sceptical senior engineer.
- **First-time reader:** Claude subagent, read-only, acting as a supervisor new to the project.
- **Advisor:** GPT-6 Astra (`gpt-6-astra`) through `codex exec --sandbox read-only` (codex-cli 0.167.0). The bounded prompt and full reply are in `reviews/`.

The v1 review record (four text reviews, 13 Nov morning) is superseded by this one. Its fixes were carried forward.

## Substantive findings and resolutions

| # | Source | Finding | Resolution |
|---|---|---|---|
| 1 | Adversarial (blocker) | The fresh task's operator objective prescribed most of what the talk credited to the capsule: fill first, prerequisites off, build once, one screen and one ABBA, no tuning. The agent's decisions cite the operator. | **Fixed.** Trace now has a legend (operator / capsule rule / agent) and recoloured steps. The "Why this is the CC at work" note was removed. The script and Q&A attribute the plan to the operator. The capsule's demonstrated contribution moved to the headline task (see 3). |
| 2 | Adversarial (blocker) | The operator reopened the task after the agent had finished (rev 9 terminal → rev 10), which is optional stopping. | **Fixed.** Trace shows rev 9 "Agent finished" and rev 11 "Operator reopens… would have become a headline if it passed". The Q&A answers the optional-stopping question directly. |
| 3 | First-time reader (most serious), adversarial, Astra | It was unclear who produced the 15.5%. | **Fixed.** Result now states that factory agent task `bd173c08` (GPT-6.1 Sol) grew plain llama.cpp component by component and built the image, and that J-OM13 was a separately specified experiment on it. Evidence links added. |
| 4 | Adversarial, Astra | The claim that a script couldn't encode dependencies or dormant rules was a false dichotomy. | **Fixed.** The text now says "A script could encode the same rules; the capsule is where they are written, versioned and found". Lesson 1 is now grounded in measured regressions from `bd173c08` (894 → 1825, 928 → 1494 ms/token). |
| 5 | Adversarial, Astra | Stock behaviour was described as serial one-page faults, and fill's random-advice effect was omitted. | **Fixed.** The diagram and script now say "synchronous page faults (with kernel readahead) inside the matmul" and add "fill also switches expert ranges to random-access advice at decode". The claim is now "how and when weights are read". |
| 6 | Adversarial | The J-OM13 headline ran on a warm cache with start residency not recorded, and it predates contention recording. | **Fixed.** Stated on Result (cold start ≈1290 ms/token, per `EVIDENCE.md`) and in the Q&A. |
| 7 | Adversarial | The four earlier failed attempts, the three agent sessions and the mid-task `baseline-import` command were undisclosed. | **Fixed.** All three are disclosed in Trace, Replay and the Q&A. |
| 8 | Adversarial | "Keeping it would be choosing a result we hoped for" fails once you ask whether the gate can pass at all. | **Fixed.** Replaced with a gate-power answer. Noise-aware replication added as an RSI target. |
| 9 | Adversarial | "Recursive self-improvement" was implied to exist. | **Fixed.** The close and the Q&A say it is the next phase and that no iteration has run yet. |
| 10 | Adversarial | The faster `-t 4` arm was hidden. | **Fixed.** Result names it and explains its exclusion (no plain `-t 4` counterpart). Q&A answer added. |
| 11 | Fact-check | A missing `HANDOFF.md`, a missing `reviews/` folder, and code cited in MODEL-CONFIG that was not yet committed. | **Fixed by packaging:** HANDOFF.md written, `reviews/` included, controller change committed and the source bundle re-pinned. Verified in VALIDATION.md. |
| 12 | Fact-check | Commit attribution was wrong: jobq exclusivity is `585cb23` (not `e410103`), and the watchdog invalidation is `322f14b7`/`fadb1fe3` (not `5b2830fb`). | **Fixed** in Lessons, the script and ENGINEERING-DETAILS. |
| 13 | Fact-check | The watchdog causality was overstated (33 MiB/s was the observed rate, the limit was 20, the run was not killed), and the rev 8/9 revert citation was imprecise. | **Fixed** wording, and cited rev 9 for the executed reverts. |
| 14 | Fact-check, Astra | "Expert weights (22.4 GB)" is really the whole file; `allowProviderModelFallback` is in service.py; section references were imprecise; the plan was edited at rev 4–11, not 6–9; the 165 s build is unverifiable from the package. | **Fixed.** Text now says "model file". The other references and section numbers are corrected. The build time is now 284 s queue-to-result per the attempts table, with the worklog's 165 s noted. |
| 15 | First-time reader | Undefined terms: ABBA, null, gate, JiuwenSwarm, factory, contract, MoE, mmap, page cache; the slice was absent from the main talk; identifiers were opaque. | **Fixed.** ABBA and null are defined on Trace and in the script. CC, JiuwenSwarm, factory and contract are defined on Result. MoE and mmap are glossed on Engine. The engine slice is named on Engine. The patch-to-component mapping is spelled out. "Satay" was removed from the header. |
| 16 | First-time reader | The Trace and Result script segments were over-dense (about 160 wpm). | **Fixed.** Segments are now 68 / 84 / 96 / 39 / about 65 words, about 115 wpm. A human spoken rehearsal is still the presenter's task. |
| 17 | First-time reader | 6:46 of mostly silent video is 68% of the talk. | **Justified, not changed.** The operator asked to keep the existing full recording at normal speed. It carries on-screen captions and compression labels, and the notes give brief narration cues. Shortening it would mean re-cutting evidence, which was out of scope. |
| 18 | Astra | Output agreement in J-OM13 might be among runs only, not against a frozen reference. | **Checked; claim retained.** All 12 hashes `7a1541792364` are the prefix of the frozen `qwen36-bare-greedy-v1` reference `7a154179236463bc…` (`contracts/qwen36-bare-greedy-v1.json`). Result now cites the reference prefix. |
| 19 | First-time reader | There is no quantified cost or benefit (agent time vs original engineering effort). | **Justified.** That was not measured, and no claim is made. The close is limited to what is demonstrated. |

## Not changed

- The historical record (evidence and `context/historical/`) is untouched. Run 5 stays excluded.
- No new experiments were run in response to any finding.
