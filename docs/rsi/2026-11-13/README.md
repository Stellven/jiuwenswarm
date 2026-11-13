# RSI assignment, 13 Nov 2026 (Satay)

**For:** the RSI person working on Satay.
**Scope:** one small RSI task (plus a fallback) on the actual capsules and recorded evidence. This is not a new optimization campaign.
**Frozen demo:** the demo stays as it is:
- tags `cc-rsi-v1`, `cc-demo-incremental-v1` and `cc-baseline-2026-11-12` stay where they are;
- the v1, v2 and v3 demo packages are unchanged.

The distinction:
- **Factory** applies capsules to improve an engine within a task.
- **RSI** changes a reusable capsule so that later applications perform better.

## Recommendation

| | Capsule | Why |
|---|---|---|
| **Primary** | `factory.builder` 1.0.0: cross-task, content-addressed build reuse | 18 of the 24 recorded successful builds (75%) rebuilt a source tree that had already been built successfully with identical inputs. That cost 4,006 s, about 67 min of exclusive build-queue time. Every evaluation step runs in seconds without a GPU, and the hard correctness checks are mechanical. |
| **Fallback** | `factory.methodology_ab` 1.0.0: power-aware stopping and decisions | Under the noise known at decision time, all 5 recorded `expert_fill` nulls were underpowered: 12–67% power at an 8% effect. AB.md still treated each one as "does not help" and reverted. The evaluation runs in seconds to a minute without a GPU. |
| Not chosen | A narrow expert-streaming component (fill or inflight) with a local benchmark | The only cheap direct benchmarks (`io_bench`, expert replay) depend on page-cache state on an 8 GB host, and resetting it reliably needs root. Duplicate-read counters exist (J-XS2-smoke), but that A/B was `INVALID`. A component result would need an engine-level ABBA before anyone could trust it, and that takes the most lab time. |

**If time is short and lab runs must be fast, pick `factory.builder`.**
- Iterating on it needs no GPU time at all.
- Its benefit also speeds up later lab work: builds and GPU jobs share one exclusive queue, so every skipped build of about 3.5 min lets the next lab run start sooner.

---

## Primary: `factory.builder` build reuse

### Frozen version and files RSI changes

**Frozen baseline:** jiuwenswarm tag `rsi-assignment-2026-11-13` (branch `cc-siminfeng`). At that tag the builder is capsule `factory.builder` **1.0.0**.
- Since `cc-rsi-v1`, the builder implementation has changed in one place: the PATH merge in `builder.py`.
- The capsule manifest is unchanged.

Files to change:
- `jiuwenswarm/factory/builder.py`, `Builder.submit`: the reuse lookup. Today it runs only inside the current task and is keyed by `jobs.fingerprint`.
- `jiuwenswarm/factory/build_job.py`, `prepare()`: it already probes `nvcc`, `gcc`, `cmake`, `ninja`, `ccache`, JetPack, L4T and the base runtime image digest, so it can supply the toolchain identity.
- `jiuwenswarm/factory/ccs/builder/cc.yaml`: version bump to 1.1.0, and document the reuse semantics in `submit.does`.
- Receipts: a reused result must say `reused_from: <attempt>` with the original commit and image. It must never pretend a new build happened.
- `tests/factory/test_builder.py`: new tests on the existing fake-toolchain fixture. The current 13 tests take 17 s.

### Weakness shown by existing evidence

The evidence is `fixtures/builds.json`, exported from `~/.jiuwenswarm-factory/factory.sqlite`. Run `python3 -I eval/builder_reuse_eval.py --key baseline` and then `--key oracle`.

| Source tree | Successful builds | Tasks | Seconds each |
|---|---|---|---|
| `2265e2c6` (plain llama.cpp) | 7 | 5 | 205–257 |
| `43f95b17` | 4 | 4 | 197–233 |
| `c9ddd710` | 4 | 4 | 192–220 |
| `d63f6127` (fill candidate) | 4 | 4 | 199–284 |
| `86ed6e38` | 3 | 2 | 195–241 |
| `29717242` | 2 | 2 | 192–208 |

**Same inputs every time.** Within each tree group, the recipe hash, engine-script hash, target, toolchain and base image are all identical. Only these fields differ:
- `commit` (for example after a revert, or a new integration commit with the same tree);
- `tag`, `deadline_s`, `node_id` and the `PATH` string;
- the task ID that `argv` carries.

The frozen key includes every one of those, so reuse never fires.

**Measured result:**
- The frozen builder reuses 0 builds.
- A strict-identity key would reuse 18, saving 4,006 s of 5,278 s (76%), with 0 false reuses.

**Concrete case:** `proof-ask-1` (task `cc5e8585`, build `3445e556`, 266 s) rebuilt tree `d63f6127`. That tree had been built by `e5b8d4b7`'s build `110a3bc4` four hours earlier.

**Same tree, same behaviour:** the two builds have different image IDs (`405eb5e7`, `a15f04f0`), because the builds are not bit-reproducible. Both produce the frozen `qwen36-quick-v1` output `cad62aa93e81` (factory evaluations).

**Latent correctness bug in the frozen builder:** the mutation check shows the frozen key **does not change when nvcc, gcc, JetPack or the base runtime image changes**. `prepare()` records those, but they are not part of the key. A retry in the same task after a toolchain upgrade would reuse a stale image. The RSI change must close this hole; it isn't allowed to widen reuse without it.

### Proposed improvement, and why it belongs in the capsule

Reuse an admitted, successful build from **any task in the same factory store** when the strict build-input identity matches:
- source **tree**, not commit;
- `recipe_sha256`, `engine_sha256`, `target` and the patch hash;
- the resolved toolchain identity (version output of nvcc, gcc, cmake and ninja; JetPack; L4T);
- the base image **digest**.

**Requirements:**
- The image must still exist locally (`docker image inspect <id>`). If it was pruned (see `artifacts/factory/PRUNED.md`), fall back to a real build.
- Record the reuse explicitly in the attempt and the receipt.

**Why the capsule:** every task, agent and operator goes through `factory.builder.submit`. Putting the rule there makes every later factory application faster. The agent doesn't have to remember to reuse, and the factory can't do it unsafely. A prompt hint, by contrast, would be neither enforced nor verifiable.

### Fast evaluation

**1. Offline replay** (about 0.1 s, no GPU or Docker). Your key function sees only the inputs available at submit time, never outcomes.

```sh
cd docs/rsi/2026-11-13
python3 -I eval/builder_reuse_eval.py --key baseline          # 0 hits, mutation check FAILS (exit 1)
python3 -I eval/builder_reuse_eval.py --key oracle            # upper bound: 18 hits, 4006 s, 0 false hits
python3 -I eval/builder_reuse_eval.py --key mykey.py:reuse_key --rows
```

**2. Unit tests** (under 30 s, fake toolchain and fake Docker):

```sh
.venv/bin/python -m pytest tests/factory/test_builder.py --no-cov -q
```

Add tests for:
- cross-task reuse with a different commit but the same tree;
- no reuse when the toolchain or base digest changes, or when the patch differs;
- fallback when the image is missing;
- receipt provenance on a reused result;
- that an idempotency-key conflict still raises.

**3. Live check** (about 10–15 min, CPU and Docker only, **no GPU**). Not yet executed. It needs the build queue to be free, so tell anyone doing timed runs before you start, because a compile spoils their measurements.

Use a scratch `FACTORY_HOME`, and take the llama source from the v3 package bundle (`sources/llama-engine.bundle`, branch `proof-ask-1`, tree `d63f6127`).

| Step | Build | Baseline expectation | Candidate expectation |
|---|---|---|---|
| a | Task A builds commit C1 (tree T). | Real build: the **clean-key** time with a warm host (ccache and base image present). | The same. |
| b | Task B builds C2 = `git commit --allow-empty` on C1 (same tree T, new commit). | Real rebuild: the **cached** time (ccache now warm from step a). | **Reuse**, with `reused_from` set to step a's attempt. Record the submit-to-result time. |
| c | Task C builds C3 = C1 plus a one-line change to a user-visible string in `tools/main/main.cpp` (tree T′). | Real build. | **Must build.** Then check that the marker is in the binary: `docker run --rm --entrypoint sh <image> -c 'grep -rlaF <MARKER> /app /usr/local/bin 2>/dev/null \| head -3'`. |
| d | Task D builds C1 again with `CUDA_HOME` / toolchain identity changed (for example a wrapper nvcc printing a different version, or a stub `prepare` result in a test-only path). | Real build. | **Must build.** The toolchain is part of the key. |

Compare the candidate's step b with the **baseline's step b**, both warm. Never compare it with step a: that would be a cold baseline against a warm candidate.

**Metric:** build-queue seconds per task, measured with the same workflow, store contents and host cache state.

### Correctness constraints

- **0 false reuses.** The offline replay must exit 0, and steps c and d must build.
- **A reused image must be admitted:** same target, image present, its original attempt succeeded.
- **Provenance stays truthful.** The binary's embedded build-info names the original commit, not the new one. The receipt must say so, and evidence must never claim the image was built from the new commit.
- **Idempotency semantics are unchanged.** The same `idem_key` with different inputs still raises `KeyConflict`.
- **Failed builds are never reused.**

### Ways the metric could mislead

- The recorded durations already include warm ccache and base-image caches. The headline saving is an **upper bound on queue time**, not a CPU-time measure.
- An over-loose key gets a perfect saving and is wrong. That's why the mutation check is a hard gate, and why only fields proven non-semantic are allowed to vary.
- The recorded history is one host, two days, and 6 trees. Later workloads may repeat less, for example tuning tasks that change the tree every time.
- A reuse that skips the build also skips `prepare()`'s disk and toolchain checks. Keep the cheap probes, because the key needs them anyway.

### What the local result establishes, and what still needs the engine

**Established:** the factory stops repeating identical work, and it does so safely: the key changes when any of its tracked build inputs change (mutation check), and the replay found 0 false reuses. With the live check, it also shows real submit-to-result times.

**Not established:** anything about engine speed. Reuse never changes the engine. For a final check, run one quick-contract screen (`qwen36-quick-v1`, about 2 min of GPU) on a **reused** image, and require stdout `cad62aa93e81…`. That's the only engine-level run this task needs. No tokens/s claim should be made.

**Acceptance:**
1. The offline replay exits 0, has 0 false hits, and gets at least 16 of the 18 oracle hits.
2. The unit tests pass, including the new ones.
3. Live steps b–d behave as in the table above.
4. The one screen of a reused image matches the frozen reference.
5. The receipt shows `reused_from`.
6. Bump `factory.builder` to 1.1.0, and record the result in `RESULT.md` next to this file.

---

## Fallback: `factory.methodology_ab` power-aware decisions

### Frozen version and files RSI changes

**Frozen version:** methodology `factory.methodology_ab` **1.0.0**. Its files are byte-identical to `cc-rsi-v1`.

| What | File | Note |
|---|---|---|
| Methodology | `jiuwenswarm/factory/ccs/methodology_ab/AB.md` | Steps 6, 7, 9 and 10: replication, gate reading, keep/revert, stopping. Step 6 currently says "repeat complete rounds". |
| Gate | siminfeng `cc/abrun/gate.py` @ `e410103` | The referee. AB.md says changing scoring rules **requires a new contract ID and a fresh reference**. A new gate is allowed only that way, and the frozen gate stays as it is. |
| Version | `jiuwenswarm/factory/ccs/methodology_ab/cc.yaml` | Bump to 1.1.0. |
| Agent tool (if wanted) | `ab.py` | A `plan` helper the agent can call before `ab_submit`. |

### Weakness shown by existing evidence

Run `python3 -I eval/ab_decision_eval.py` (about 10–60 s). It uses `fixtures/abba.json`: 22 recorded ABBA experiments from 10–13 Nov, split by time.

**Finding 1: the frozen gate loses power as rounds are added.** The threshold is `2 × max within-arm range / mean`, and a range widens with more samples. Detection probability at a true 8% effect:

| Rounds | Noise from the training split | Noise from the validation split |
|---|---|---|
| 1 | 0.85 | 0.45 |
| 2 | 0.61 | 0.09 |
| 4 | 0.28 | 0.00 |

So AB.md's own advice, "repeat complete rounds", lowers the chance of detecting a real effect.

**Finding 2: real effects are thrown away.** `expert_fill` has a consistent benefit:
- improved in J-OM8b, J-OM9, J-OM10, J-OM10b and factory run `f19094c8`;
- part of the J-OM13 headline.

Yet it was rejected 5 times on nulls with ratios between 1.04 and 1.12. At each of those decisions, power at 8%, computed from the noise known **at that moment**, was between 0.12 and 0.67. Each rejection was a negative claim the evidence did not support. The frozen policy scores 5 unjustified negative claims and 0 harmful keeps.

### Proposed improvement, and why it belongs in the capsule

**(a) Before dispatching:** estimate power for the planned design from recorded host noise for this contract.

**(b) After a null:** classify it as *powered* (a negative claim is allowed) or *underpowered* (inconclusive, no negative claim; `keep_dormant` if needed by dependents). Choose between "replicate with k rounds", "stop" and "inconclusive" within budget.

**(c) Optionally:** a gate v2 under a new contract ID whose threshold doesn't grow with sample range (for example a median or trimmed, SE-scaled threshold or a sign-consistency rule). It must keep a false-improvement rate of 5% or less.

**Why the capsule:** every factory task that runs an A/B reads this method, so fixing it fixes every later decision. As things stand, any agent following AB.md will reject real effects on this host.

### Fast evaluation

```sh
cd docs/rsi/2026-11-13
python3 -I eval/ab_decision_eval.py                                              # frozen gate + AB.md 1.0.0
python3 -I eval/ab_decision_eval.py --policy examples/power_aware_policy.py:decide   # illustrative rule only
python3 -I eval/ab_decision_eval.py --gate my_gate.py:evaluate --policy my_policy.py:decide
```

**Inputs:**
- **Train:** before 12 Nov 00:00Z (J-OM8–J-OM11). Fit noise models and rules here.
- **Validation:** later sets (J-OM12, factory lab runs, J-OM13, J-ASK1). Don't tune on them.

**Outputs:**
- Part 1: false-improvement rate and power by rounds, with train noise and validation noise shown separately.
- Part 2: for each held-out comparison, the gate verdict, the **action**, and a rubric judgment.

**Rubric:**
- `keep` requires gate `improved`. Keeping a harmful component is a hard fail.
- `reject` requires `regressed`, or at least 0.8 power at the minimum effect of interest.
- `inconclusive` is wrong on a clear regression.
- `replicate:k` must reach at least 0.8 power within budget.

The rubric has no single preferred answer and doesn't reward shorter output. It does count lab minutes.

**The rule makes a real difference:** the illustrative rule changes all 5 fill decisions from `reject` to `inconclusive`. Under the frozen gate, no affordable design reaches 0.8 power. That is why the gate v2 in (c) is where the real gain lies.

### Correctness constraints and ways it could mislead

**Constraints:**
- The frozen gate is never edited; a new gate means a new contract ID.
- A false-improvement rate of 5% or less on **both** noise splits.
- 0 harmful keeps.

**Ways it could mislead:**
- Residuals pool 32- and 64-token contracts and different cache states. Noise doubled between the splits (spread 1.7% to 3.4%), so the noise isn't stationary.
- The validation set is small: 17 scored comparisons, 6 of them fill.
- The labels are hindsight from pooled evidence, partly from the same experiments.
- Resampling assumes independent runs, but ABBA drift is real.
- A rule tuned to "rescue fill" is choosing a hoped-for result. Judge it on the false-improvement rate and the rubric, not on fill passing.

### What the local result establishes, and what still needs the engine

**Established:** better-justified decisions, and measured operating characteristics, on recorded data.

**Not established:** that a component kept under the new rule is really faster. That needs one pre-registered engine ABBA under the new contract ID. For fill, J-OM13 already suggests the answer, but the new gate must be shown on fresh runs. Budget about 30 min of quick-contract lab time, only if the offline results earn it.

**Acceptance:**
1. The validation run exits 0.
2. 0 unjustified negative claims and 0 harmful keeps.
3. A false-improvement rate of 5% or less on both splits.
4. Lab minutes requested no higher than needed.
5. AB.md 1.1.0 is written, with the rule in prose plus the helper.
6. `RESULT.md` records the train and validation numbers separately.

---

## Reproduction on Satay

```sh
git clone -b cc-siminfeng git@github.com:Stellven/jiuwenswarm.git && cd jiuwenswarm
git checkout rsi-assignment-2026-11-13            # frozen inputs for this assignment
cd docs/rsi/2026-11-13
python3 -I eval/builder_reuse_eval.py --key oracle   # about 0.1 s
SIMINFENG_ROOT=~/projects/siminfeng python3 -I eval/ab_decision_eval.py   # about 10-60 s; needs siminfeng gate.py @ e410103
```

**Requirements:**
- Both evaluators use only the Python standard library.
- The siminfeng clone is `git@github.com:Muxite/siminfeng.git`, branch `jetson/c1`. Ask the operator for access.
- The fixtures are self-contained. They need no access to the operator's `~/.jiuwenswarm-factory`.
- The live builder check needs:
  - Docker;
  - `/usr/local/cuda`;
  - the build queue (`systemctl --user status satay-jobq`; it runs under the operator's account);
  - the llama source bundle from the v3 package (`20261113 Satay CC Demo and Recovery v3 prepresentation.zip`, `sources/llama-engine.bundle`; restore it with `scripts/restore-sources.py`).
- Do the work on your own branch from the tag. Don't move existing tags.

## Files

| Path | What |
|---|---|
| `fixtures/builds.json` | 29 recorded build attempts: requests, toolchain probes, durations, image IDs |
| `fixtures/abba.json` | 22 recorded ABBA sets: per-run ms/token, contract, component, frozen verdicts |
| `eval/builder_reuse_eval.py` | Primary: offline reuse replay plus mutation check |
| `eval/ab_decision_eval.py` | Fallback: gate operating characteristics plus decision rubric |
| `examples/power_aware_policy.py` | Illustration that actions change; not the RSI result |
| `ANOTHER-HOST.md` | How to reproduce a CC win on a second machine |
