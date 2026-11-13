# 20261113 Two Engineering Details prepresentation

Both details come from the actual implementation and records. Paths beginning `evidence/` and `context/` are inside this package. Repository paths name the repository and commit.

## 1. A source dependency is not a runtime enablement

**Source fact.** Demand fill (`expert_fill`, patches 03-05) runs inside a CPU-only callback before the first expert matmul of each layer. That callback, `ggml_backend_sched_set_cpu_callback` / `expert_prefetch_cb`, is added by the `router_prefetch` patch (02), which builds on `mmap_advice` (01). Sources: `context/expert_streaming/SOURCE-MAP.md` §1 "Hook points" and §2 "02 router_prefetch". So fill needs both patches in the source tree.

**Measured fact.** These measurements come from the agent task that built the headline image: `evidence/factory-run4/`, task `factory-bd173c08`, 12 Nov, GPT-6.1 Sol. Each component was integrated, built and ABBA-tested on its own:

| Component (switch on) | Baseline → candidate, ms/token | Gate | Agent action |
|---|---|---|---|
| `mmap_advice` | 893.71 → 1824.81 | regressed | rev 6 `keep_dormant`, `needed_by` router_prefetch, expert_fill, … |
| `router_prefetch` | 928.23 → 1494.15 | regressed | rev 10 `keep_dormant`, "Source patch 02 is required by expert_fill; switch defaults off" |
| `expert_fill` | 918.23 → 827.29 (ratio 1.110) | improved | rev 14 `keep_component` |
| `expert_pregate` | 831.26 → 738.64 (ratio 1.125) | improved | rev 18 `keep_component` |
| `thread_names` | gate not measured (observability) | — | rev 22 `revert_component` |

The final image (`0b514fba`, restored as `bd173c08-restored-0b514fba`) is the one J-OM13 later measured. Source: `evidence/factory-run4/records/decisions.json` and `STORY.txt`.

**The rule the agent applied.** jiuwenswarm `jiuwenswarm/factory/ccs/methodology_ab/AB.md` step 9, the dormant-prerequisite exception: "if a rejected component's source is required by components not yet measured and its switch is off by default, you may keep its commit with the switch OFF in every later arm and publish keep_dormant… If a dependent is later rejected too, revert both in reverse order." The fill component declares the same dependency and its off switches (`context/expert_streaming/components/expert_fill.component.yaml`):
- `depends_on: [mmap_advice, router_prefetch]`
- `enable_env` sets `LLAMA_EXPERT_PREFETCH: '0'`, `LLAMA_EXPERT_PREFETCH_NEXT: '0'` and `LLAMA_MMAP_ADVICE: default`, while setting `LLAMA_EXPERT_FILL: '1'`

**In the fresh recorded task** (`evidence/incremental/decisions.json`):
- The operator objective prescribed "source prerequisites installed but their switches off".
- The agent committed `733364f0d` (mmap_advice), `c0da1c0b1` (router_prefetch) and `00c6038f1` (fill).
- The engagement checks tested fill only.
- When the fill gate was null, rev 8 decided to revert because "no dependent remains to justify dormant retention". Rev 9 records the executed reverts (`384182aa`, `2a3757a3`, `b7910f72`) and the tree back to plain `cf34d311` (tree `2265e2c6`).

**Consequence.** Switching every applied patch on would have made decode roughly 1.6–2× slower than plain in these measurements, and it would have hidden which mechanism helped. The dependency, the off switches and the rollback order are written into the capsule as checked data. A script could encode the same rules; the capsule is where they are recorded, versioned and found by the agent.

## 2. A compiler running beside a measurement can spoil it

**Observation.** On 10 Nov, the first over-memory run on Satay was recorded as **unscored because a C++ build was compiling concurrently**. During that run the memory watchdog also tripped on its swap-rate limit: the observed rate was 33 MiB/s against a default limit of 20 MiB/s, which D029 judges "not dangerous; default 20 too tight". The run nevertheless exited 0 because the watchdog's kill command was broken, which was fixed separately. Sources (siminfeng):
- `decisions/D029-first-over-memory-run-and-watchdog-fix.md`
- `CLOSEOUT.md` row `feas-b1-a2`
- `CLOSEOUT.md` §5.6: "One GPU job at a time; builds must not overlap timed runs"

**Fixes, now in code:**

| Repo | Commit | Date | Change |
|---|---|---|---|
| siminfeng | `585cb23` | 11 Nov | `bin/jobq`; `compatible()` never runs GPU and build jobs together |
| siminfeng | `e410103` (merge c2/heavy-guard) | 12 Nov | `bin/heavy` routes compiles through the queue's build class; `cc/om_run/contention.py` records foreign compile processes for every run; `cc/abrun/gate.py` adds "`<arm>: host_contention`" to the invalid-scoring reasons. Tests: `cc/abrun/test_contention.py::test_contention_invalidates_gate`, `bin/test_heavy.py` |
| jiuwenswarm | `5b2830fb` | 12 Nov | `jiuwenswarm/factory/jobs.py` defaults factory build and lab jobs to the host's shared queue |
| jiuwenswarm | `322f14b7`, `fadb1fe3` | 12 Nov | Watchdog-tripped or OOM runs are invalid in `factory/ab.py` and `factory/lab_runner.py`. Test: `tests/factory/test_lab.py` with a tripped-watchdog fixture |

**What the record shows for the fresh task** (`decisions.json` rev 11): "All 12 summaries status ok and host_contention false, foreign heavy count 0." Its single build (attempt `110a3bc4`, 284 s from queue submission to result per the attempts table; the worklog records a 165 s build) went through the same queue as the lab jobs. J-OM13 (12 Nov, before `e410103`) has no contention records.

**Consequence.**
- Queue discipline is part of the measurement method.
- More repeats would not have exposed this interference.
- A contended run is now marked unscored instead of being averaged in.

## Spare detail: the setting you asked for is not always the setting that ran

- **Incident.** In J-OM10c, an arm requested predictive-read K=10 but ran K=8 because the parser fell back silently (siminfeng `c2/MEASUREMENT-GAPS.md` §4). The "active" regex passed anyway.
- **Fix.** Components now print one effective-config line, and jiuwenswarm `jiuwenswarm/factory/inspector.py` `verify()` compares requested and effective settings (`CONFIG_MISMATCH`, `CONFIG_MISSING`). Test: `tests/factory/test_capsules.py::test_effective_values`.
- **In the fresh task.** The fill-only build lacks that line, so the effective-config checks were reported as 0/2 *unmeasured*, not passed (rev 5). In rev 7 the agent also used the authoritative 32-token contract instead of a stale 64-token resource note.
