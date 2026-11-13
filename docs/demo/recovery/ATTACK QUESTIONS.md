# 20261113 Demo Attack Questions prepresentation

## The five questions to expect

**How did you find this?**
- **Discovery:** earlier engineering on this board, through source inspection, lab runs and failures. Siminfeng's records show stock llama.cpp stalling on page faults inside CPU expert matmuls (D029 onward), and demand fill and predictive reads were built and measured there (the J-OM series).
- **Packaging:** that knowledge became `engine.expert_streaming`: guide, source map, evidence rules, and patches with their dependencies and checks.
- **Application:** on 12 Nov, factory agent task `bd173c08` (GPT-6.1 Sol) applied the components one at a time to plain llama.cpp and built the headline image.
- **Measurement:** J-OM13 was a separately specified experiment on that image.
- **Not claimed:** no agent invented the technique in this demo.

**What does the CC contribute?**
Written, reusable engineering knowledge and the components that implement it:
- applicability
- the patches and their declared dependencies
- runtime switches and engagement checks
- how to judge a measurement: ABBA order and a noise-based gate
- correctness against a frozen output reference
- revert and dormant-prerequisite rules
- stop rules

**What it demonstrably changed:**
- In `bd173c08` the agent measured both prerequisites as slower when enabled (894 → 1825 and 928 → 1494 ms/token). It still kept them in source with switches off, because fill needs patch 02's hook. That is the capsule's rule, recorded as `keep_dormant` at rev 6 and rev 10.
- In the fresh recorded task the capsule supplied the patches, checks, gate and revert order.
- In the fresh task, the **operator's objective** prescribed the order and procedure (fill first, prerequisites off, one build/screen/ABBA, no tuning). We don't credit those to the capsule.

**Why not raw Codex or a script?**
- **A script:** it could encode the same rules. The capsule is where those rules are written down, versioned, checked (`component.yaml`, `AB.md`) and found by an agent, together with source maps a script doesn't need to understand.
- **Raw Codex:** we have not compared it against raw Codex given equivalent context, so we claim no speed or quality advantage.
- **What is demonstrated:** a reusable, versioned package, plus durable build/lab records that make every decision traceable to source, image and evidence.

**Does the ontology affect execution?**
- **Execution:** no. It names engine boxes (router, selected experts, CPU expert execution, page cache…) and the quantities that measure them.
- **The new link:** since 13 Nov 07:36 (`6d10c8c5`, capsule 2.0.1), a new task can name the slice `expert_weight_readiness`. The factory validates the name and attaches it, with the contract reference, to the seeded work nodes. Later plan edits that carry it are validated, and an unknown name is rejected.
- **What it does not do:** dispatch, build, score or accept anything, or prove that a code edit stays inside the slice.
- **History:** the recorded runs predate the link and used capsule 2.0.0.

**What can RSI improve?**
"RSI" here means agents improving the capsule itself. That is the next phase, and **no such iteration has run yet**. Its starting point is the frozen tag `cc-rsi-v1`, which is unchanged. Genuine opportunities:
- **Noise-aware replication and gate power.** The current gate uses twice the max-min A/A range, which never shrinks with more runs. On this noisy host the 3-round confirmation could hardly have passed.
- **Intervention ordering:** when to try predictive reads straight after a positive fill screen.
- **Adaptive expert-read policy:** queue depth, chunk size, lookahead.
- **Effective-config coverage:** fill-only builds lack the effective-config line.
- **Warm/cold cache protocol** for headline claims.
- **New capsules:** CPU/GPU placement and KV-cache memory.

## Follow-ups a sceptic may raise

| Question | Answer |
|---|---|
| Did this video achieve the headline? | No. It is the fresh 32-token fill-only task, which was inconclusive. The headline is the separate 64-token J-OM13 experiment on the image built by `bd173c08`. |
| The operator wrote the plan. Where did the agent matter? | Its own calls in the fresh task: it repaired the branch to the requested base (rev 1), worked around a missing git identity (rev 2), and reported the effective-config check as unmeasured instead of assuming it (rev 5). It also stopped rather than compare against an unverifiable baseline (rev 6) and caught a stale 64-token note, using the real 32-token contract (rev 7). In `bd173c08` it chose the order from component dependencies and applied the dormant rule after measuring regressions. |
| You reopened a finished task to get another chance. Isn't that optional stopping? | Yes, it was a human decision after the agent had finished (rev 9 → rev 10). It came back null, and both trials are reported, not pooled. The capsule itself advises against rerunning for a prettier number. |
| Can your gate even pass on this host? | It is deliberately conservative: the threshold is twice the largest within-arm spread. With 12.8% A/A noise, an 11–12% effect was undetectable. Null means "not shown", not "no effect". A better replication policy is an RSI target. |
| Was the J-OM13 cache state controlled? | No. It was a warm chain with start residency not recorded. A cold start measured about 1290 ms/token (`EVIDENCE.md`). The comparison is matched and alternating, but treat the absolute numbers as warm-cache. It also predates contention recording. |
| The `-t 4` arm was faster. Why hide it? | It is in the report. It was exploratory and had no plain `-t 4` counterpart, so its extra gain can't be attributed to the capsule. We report the default-thread pair only. Thread count is an open question for absolute numbers. |
| How many attempts did the recording take? | Five. Four stopped on infrastructure: disk space, a host crash, a resume error, and a queue worker that didn't restart after reboot. All are kept, and they are why the recovery work exists. |
| Was the harness changed during the task? | Yes. The operator wrote `factory baseline-import` after the agent stopped on the missing baseline record. The task continued in a new agent session, so three sessions in total. |
| Is the model now more accurate? | No claim. We checked byte-identical greedy output on fixed workloads only. |
| Why this model and machine? | The model file (22.4 GB) is almost three times the 7.4 GiB of shared memory. The capsule's applicability check confirmed that expert bytes exceed RAM with experts on the CPU. A model that fits in memory may gain little. |
| Where does the improvement happen? | In how and when selected expert weights become resident before the CPU expert matmul: parallel reads, plus random-access advice at decode. CPU/GPU placement is unchanged. |
| Is recovery automatic? | Partly. A worker restart under systemd (Linger=yes) and interrupted-job reconciliation were tested. A physical reboot and power loss were not. |
| Which model ran the agent? | GPT-6.1 Sol (`gpt-6.1-sol`) through the factory's pinned Codex 0.163.0, according to the factory's Codex thread records. See `MODEL-CONFIG.md`. |
