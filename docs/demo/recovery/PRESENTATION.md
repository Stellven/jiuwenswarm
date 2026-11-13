# 20261113 Satay Ten Minute Demo prepresentation

Audience: engineering supervisors and colleagues familiar with agents, but not this engine or factory. Goal: they understand what the CC contributes, where it changes the engine and why further CC development is worthwhile.

## Timed sequence

Use the launch console. Keep the existing full 6:46 video at normal speed. The narrative around it totals 3:14. The original recording retains its readable pauses.

| Time | Console view | Say or do |
|---|---|---|
| 0:00–0:35 | Result | A capability capsule, or CC, packages reusable engineering guidance and components. Here it prepares expert weights before computation. A recorded comparison reduced decode time from 841.5 to 711.4 ms/token. |
| 0:35–1:35 | Engine | Explain that a mixture-of-experts (MoE) model uses selected experts for each token. A memory-mapped file (mmap) lets the engine access stored weights through memory addresses. Explain CPU expert execution and the before-matmul read hook. The CC changes when expert weights arrive; it does not move these experts to GPU memory. |
| 1:35–2:35 | Method | Show the task target versus fixed lab contract. Prior engineering supplied the technique; this replay tests reuse. Demand fill was selected and built with dormant mmap/router prerequisites. The screen reported 6.27 GB read, establishing activity, but the baseline/candidate/candidate/baseline comparison did not clear its noise threshold, so the agent stopped. A separate earlier incident showed why builds and measurements now share one queue. |
| 2:35–9:21 | Replay | Play the 6:46 recording. It shows a different, fresh fill-only task whose final result is inconclusive. Operators imported the baseline and authorized confirmation; those interventions remain visible. |
| 9:21–10:00 | Result | Return to the separately labeled historical result. Explain the value of reusable guidance and traceable execution, then hand over the unchanged capsule baseline for recursive self-improvement (RSI). |

The screen timer is a rehearsal aid, not a benchmark timer. Browser video playback is a recording, not live execution. A timed playback check validates runtime; a human's spoken rehearsal remains recommended.

## Two engineering details worth remembering

1. Source dependency is not runtime activation. The fill-only candidate includes dormant mmap/router prerequisites, while fill is the active change. Show the configuration and source ancestry in evidence/incremental/results.json. This is why a CC needs methodology and integration knowledge, not just a patch list.
2. A build can invalidate a measurement. Earlier concurrent compilation increased memory pressure enough to trigger a watchdog. The factory now routes heavy work through the shared queue and marks a contended measurement unscored. Show the code change/test references in context/recovery rather than implying that more repeats alone solve interference.

## Exact result wording

J-OM13 is a recorded matched experiment with three arms and four runs per arm. The headline uses base and factory: eight relevant runs; the third four-run thread-count arm is retained in the raw report but not used in the headline. Means: 841.4975 and 711.425 ms/token. Derived: 15.457% less time/token, 18.283% higher throughput. Its existing gate says improved; this is not a general accuracy or cross-hardware claim. Output matched the fixed reference.

The fresh 32-token fill-only comparisons did not clear their gates. Never substitute their best run, multiply ratios across experiments or imply the recording produced the J-OM13 result. Some archived summaries loosely mix speed and latency percentages; use these source means and the canonical wording above.

## Provenance and future value

Human/agent engineering work supplied the expert-streaming techniques, integration materials and contracts. JiuwenSwarm applied and evaluated packaged capability knowledge; it did not autonomously discover all techniques in this demonstration. No controlled comparison establishes superiority over a raw coding agent. Demonstrated value is explicit reusable guidance, durable builds, image/evidence traceability and revisable decisions. RSI can improve that reusable capsule; this factory improves an engine within a task.
