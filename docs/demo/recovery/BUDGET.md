# Satay demo continuation budget ledger

Ceilings: 6 h total wall time and 2 h cumulative lab occupation. These include waiting and failed work, and they do not reset on a restart or a new prompt.

No ledger existed before 08:49 UTC on 13 Nov. The charge below is reconstructed conservatively from records on the host. Satay has no RTC, but the clock has been continuous since boot at about 00:48.

| Stage | Start (UTC) | End (UTC) | Wall | Lab | Basis |
|---|---|---|---|---|---|
| Earlier continuation (packaging v1) | 07:10 | 07:57 | 0.78 h | 0 | Starts at the last handoff commit `c8e4b2ce` (07:10:25) and ends with the Danta copy (07:57). No queue job ran after 03:38. |
| Gap before this session (charged anyway) | 07:57 | 08:29 | 0.53 h | 0 | Conservative: the idle time is counted. |
| This session: mount, read, plan | 08:29 | 08:49 | 0.33 h | 0 | Danta mounted, instructions read, plan approved. |
| **Charged at 08:49** | | | **1.64 h** | **0 h** | |

Hard stop for this continuation: 12:40 UTC, which leaves about 0.5 h of margin under the 6 h ceiling. The plan authorises no lab work, and none has been used.

## Later stages

| Stage | Start (UTC) | End (UTC) | Wall | Lab | Basis |
|---|---|---|---|---|---|
| v2 work: preserve generators, checkpoint, console and engine diagram, browser checks, engineering details, script and Q&A, four reviews and fixes, tests, validation docs | 08:49 | 09:17 | 0.47 h | 0 | No lab or build job was submitted. The only model calls were the four reviewers (three Claude subagents and one GPT-6 Astra advisor). |
| **Charged at 09:17** | | | **2.11 h** | **0 h** | |

| Package (re-pin, restore check, zip), Danta copy and direct-I/O verification, commits and push | 09:17 | 09:26 | 0.15 h | 0 | — |
| **Final charge** | | | **2.26 h of 6 h** | **0 h of 2 h** | Stopped at completion; no time consumed just because it remained. |
