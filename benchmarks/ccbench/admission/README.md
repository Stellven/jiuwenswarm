# T36: tool admission before use

## Origin (ccbench copy)

Copied from cc-sweep-20261026/admission (sha256 in BASELINE-CODE-MANIFEST), changes:

- No `C:/Users` paths. Every writer takes `--out DIR` and writes only there (`study.py`, `verify_study.py`, `build_candidates.py`). The source folder is read-only.
- `study.py --reps N` (default 100, the full study). `ground_truth.json`, `declarations.json`, `SKILLS.md` and `candidates/` are copied as inputs; results and evidence files (`results.json`, `*_trials.json`, `admission_evidence.json`, ...) are not copied. They stay in the old evidence root.
- `failures_strictly_before_detection` was a hard-coded 0. It is now counted from each trial history (failures with use number below the first detected failure). The oracle is immediate, so it is still 0 by construction, and `results.json` is unchanged at 100 reps (checked, same bytes after CRLF to LF).
- `test_recorded_metrics_reconcile` now runs the study into a temp directory at 5 repetitions instead of reading stored results.
- `frozen_manifest.json` hashes the code in this folder, so it differs from the old one by construction (different bytes, LF endings, new options).

Run everything through `scripts/ai4r-bench` (container `ai4r:cc-v1-baseline`, repo mounted read-only, output in `--out DIR`). Add `--host` to use the host Python. Env roots: `AI4R_CODE_ROOT` (product repo; default: this repo), `AI4R_BENCH_DATA` (old evidence root: traps, stored baselines), `AI4R_CODEX_BIN` (codex; default `codex` on PATH). Files written by the original harness had CRLF line endings on Windows; this copy writes LF, so compare old results after CRLF to LF.

```sh
sh scripts/ai4r-bench admission --reps 1 --out OUT      # 1 repetition
sh scripts/ai4r-bench admission --out OUT                # full: 100 repetitions
sh scripts/ai4r-bench admission verify --out OUT         # two full runs, hash compare, unit tests
sh scripts/ai4r-bench selftest admission
```

**Rich declared contracts rejected all 14 planted defects before consumer use;
both correct references were admitted.** Twenty ordinary uses detected a mean
7.29 defects and missed 6.71 (95% bootstrap CI 6.48–6.95) per repetition.
The deliberately thin declaration admitted all 14 defects. See
[RESULTS.md](RESULTS.md) for detection lag, intervals and every candidate.

This supports a bounded claim: sufficiently rich, executable declarations can
guide useful pre-admission tests. It does **not** show that quality can only be
judged with declarations, that a skill cannot be tested before admission, or
that passing a finite test suite proves correctness. A prose skill can supply
semantic requirements too; an undeclared tool can be reverse engineered or
tested against an external specification. Here the observation-only policy has
no such pre-use specification and cannot get evidence before invoking a tool.

## What was built

- Sixteen plain Python candidate modules in `candidates/`: one reference and
  seven general defect transformations per tool. Shared implementations are in
  `reference.py`. Defects range from common loss of signs/fractional means and
  CSV coercion to rare grammar acceptance and integer precision loss.
- One rich declaration per tool in `declarations.json`, with typed ports,
  ranges, invariants and edge policies. This is a small study contract language,
  inspired by CC declarations, **not a schema-valid installed CC release**.
  Calculate reduces one selected column; packet transport, provenance, input
  hashes and multi-column composition are outside this experiment.
- `derive_tests(declaration)` in `derive.py` returns fresh JSON-serializable
  inputs and obligations. It reads no candidate source, defect labels, files,
  global random state or usage data. Supported semantic input types determine
  the generator; renaming a tool leaves tests unchanged. Boundary partitions
  follow the declared scalar types, numeric grammar, ranges and invariants.
  The compiler supports these two semantic families, not arbitrary prose.
- `oracle.py` is the independent executor of the declared semantic assertions
  and the skill-route observational oracle. It uses Fraction and integer
  half-even rounding rather than the candidates' Decimal arithmetic. Table
  checking preserves exact scalar types; True and 1 differ. Both sides trust
  Python's CSV parser, a shared primitive and a remaining common-mode risk.
- `ground_truth.json` contains handwritten counterexamples and expected outcomes
  for every defect. It is consulted for labels and validation, never to generate
  tests, sample uses or decide admission. Tests independently verify all 14
  counterexamples against the oracle and their candidate implementations.

## Routes and measurements

CC admits iff every derived test passes. Rich contracts generate 220 calculator
tests and 50 normalizer tests **per candidate** (2,160 total invocations); they
are held out from candidate-facing examples/self-tests. Failed checks remain in
`admission_evidence.json`; no retry hides failures. The thin sensitivity keeps
typed ports/ranges but removes semantic invariants and edge policies. It derives
20 calculator and 2 normalizer tests, checking output types only. A legal error
status is structurally acceptable in this weak contract. Thin does not secretly
borrow the rich oracle's semantic promises for its admission decision.

SKILL uses the prose in `SKILLS.md` as its only description and is simulated
without a model. Its policy observes up to N=20 uses and rejects at the first
independently observable wrong result; otherwise it admits after probation.
No test generation or targeted defect probes guide these uses. Seeds are fixed
before evaluation: base 361027, per-tool offset 10,000, repetition offset 0–99.
All candidates and routes receive identical streams within each tool/repetition.

`usage.py` defines a synthetic office-data distribution: counts, amounts,
prices, refunds and occasional long IDs; 70/30 numeric/decimal calculator
inputs; 65/35 CSV/JSON imports; typical sizes 0/1/4/12 with weights 3/12/50/35.
Rare entry errors, nullable/boolean JSON values and whitespace occur at fixed
rates. Exact probabilities live in that file. They are assumed realistic, **not
measured production telemetry**, and were not fitted to detection outcomes.
The same author created contracts, mutants and sampler; no independent blind
authorship or preregistration is claimed. Source separation and pre-run hashes
reduce implementation leakage but do not remove researcher selection bias.

Admission time differs deliberately: CC is pre-use; SKILL is after probation.
Treating the probation as sandboxed would remove consumer harm for SKILL too,
but would still leave its missed defects. This simulation treats trial outputs
as delivered and gives the observational route perfect immediate error
recognition. Thus 729/1,400 defective candidate-repetitions failed visibly,
each delivering exactly one triggering failure; 671 remained right-censored
after 20 uses. Failures strictly before detection exclude that triggering output
and equal zero. Rejected CC candidates receive no consumer uses. Thin admits
all candidates then uses the same observation stream to measure exposure;
its admission decision is not retrospectively rewritten.

Lag is recorded as a use index, or null with an explicit censoring flag.
Restricted lag is min(first failure,20), with zero exposure for pre-use
rejection; that zero is not an empirical failure time. Conditional mean detected
lag is 5.47 uses and excludes misses. Bootstrap CIs resample the **100 complete
repetitions**, preserving pairing across mutants and tools (2,000 draws, seed
362026). They quantify sampling variability for this fixed mutant bank and
distribution, not generalization to other defects or specification uncertainty.
Deterministic CC intervals are degenerate. Trial budgets are unequal (220/50
derived checks versus at most 20 uses); this is not a cost-matched comparison.

**CC power depends on declaration richness and the quality of the compiler and
oracle.** The thin run demonstrates this dependency directly. Rich rules cost
authoring effort and may miss undeclared requirements. No product-runtime,
model-capability, security-certification or universal superiority claim follows.

## Source context

Read-only study sources: the authoritative `BENCHMARK-PLAN.md` and approved
`to-make-it-fair-tidy-candy.md`; repository `AGENTS.md`; capsule extensions
`calculate`, `calculate_typed`, `calculate_v2`, `table_normalize`, `generalist`,
`catalog.py`, `assets.py`; checks `admission.py`, `calibration.py`; calibration
resources; case-bank-01 calculator/normalizer cases and `native_skill/helper.py`.
The typed/v2 calculator workers delegate to the original calculator. Its
precision setting is 128 decimal digits despite the `decimal128` label.
Generalist is low trust and explicitly does not certify a specialist capability.
Catalog pins release closures; admission verifies captured host evidence and
calibration binds exact subject outputs to protected checks. This local harness
models the quality-testing question; it does not invoke those product gates.

No network, model, app HTTP, Docker, credentials or external writes are used. See "Origin" above for the run commands. `verify_study.py --out DIR` writes `reproducibility.json` and `test-output.txt` into DIR. The frozen manifest hashes implementation, declarations, prose skills and scoring code before scoring. Verification scratch
logs stay in `.scratch-reproducibility/` and are never deleted.
