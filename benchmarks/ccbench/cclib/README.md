# cclib — in-process CC stage harness

## Origin (ccbench copy)

Copied from cc-sweep-20261026/cclib (sha256 in BASELINE-CODE-MANIFEST), changes:

- Library for planner and planbench (their `import cclib`), not run on its own. `sys.path` must contain `benchmarks/ccbench`; `scripts/ai4r-bench` and `selftest.py` arrange that.
- Scratch stores and codex call evidence no longer go under `cclib/.scratch`. `harness.SCRATCH_ROOT` defaults to a temp directory (`AI4R_BENCH_SCRATCH` to override); runners point it at their `--out`. `harness.py --out DIR`, `compare_prompts.py --out DIR`, `verify.py --out DIR` write only there.
- The codex command uses `AI4R_CODEX_BIN`/PATH and fails fast if missing (`roots.require_codex`).
- Latent bug fixed: `Harness.run_stage` failed with `TypeError` when an exception carried an integer `code` (openjiuwen `FrameworkError`), hiding the real error.
- `test_ccfix.py` and `test_pass1_audit.py` are not copied: they test other benches' scorers (`night/`, `screenbench/`, `deliverbench/`) that are not part of ccbench.
- `verify.py` reads its trap export from `AI4R_BENCH_DATA`. Against the current product it reports prompt equality 3/4 (the stored comparison says 4/4); the product planner prompts have moved. This is product drift, not a harness change.
- Not copied: `prompt-comparison.json`, `test-output*.txt`.

Run everything through `scripts/ai4r-bench` (container `ai4r:cc-v1-baseline`, repo mounted read-only, output in `--out DIR`). Add `--host` to use the host Python. Env roots: `AI4R_CODE_ROOT` (product repo; default: this repo), `AI4R_BENCH_DATA` (old evidence root: traps, stored baselines), `AI4R_CODEX_BIN` (codex; default `codex` on PATH). Files written by the original harness had CRLF line endings on Windows; this copy writes LF, so compare old results after CRLF to LF.

```sh
sh scripts/ai4r-bench cclib --out OUT          # unit tests + prompt comparison against the stored trap export
sh scripts/ai4r-bench selftest cclib
```

Runs **Intent m1-7, Requirements m1-9, Screening m1-5, Evaluation m1-5,
Delivery m1-5 and Planner** from the source repository on `PYTHONPATH`.
All harness writes, SQLite databases, Codex working directories and evidence
stay under this directory. Scratch directories are retained, never removed.
No runtime service, Docker, HTTP or network is needed for scripted runs.

## What is real

- Capsule worker code, packaged prompts, public schemas and declaration ports.
  The repository asset builders verify their immutable release catalogs.
- `checks.compiler.compiler_checks` for Intent/Requirements,
  `checks.stages.ResearchChecks` for Screening/Evaluation/Delivery (including
  `science` and scientific-verdict/delivery checks), and `planning.planner_checks`.
  Bundles run through the actual `CheckRegistry.run` engine with pinned assets.
- `gate.SemanticVerifier.review`, `assemble_assessment`, actual verifier
  mechanical predicates, and `ProtectedGate.decide`, separately for every output.
  Failed mandatory deterministic checks prevent semantic calls. Blocking
  readiness/uncertainty also prevents review, following `runner.py`.
- Screening's pure ranker and pinned scoring instruction. Planner's exact worker
  bytecode, parsing, advisory diagnostics and bounded second generation.
- Exact `InvocationContext.model` transport framing:
  `system + "\n\n<subject_payload>\n" + prompt + "\n</subject_payload>"`.

## What is reconstructed

This is **offline CC logic**, not installed-runtime execution or production
admission evidence. The minimal context uses SQLiteRunStore directly. Contract,
policy/admission placeholders, invocation observation and review bindings are
locally constructed. An observation means Python returned successfully; it does
not attest a product runtime. There is no broker, scheduler, admission operation,
run-wide budget enforcement, process containment proof, acceptance transaction,
resource authorization facade, native trace or installed SDK tool environment.
The real gate evaluates this local evidence, not a production execution record.

Planner normally builds a native SDK agent and uses system TemporaryDirectory.
Its `NativePlanner.propose` dependency is replaced with a direct call of the
provided model using the worker's payload and instructions. A function with the
original `planner.execute` bytecode and copied globals performs that substitution;
the shared repository module is not patched. Planner model-boundary bytes are
therefore reconstructed and are not claimed equal to a native SDK prompt.

When worker-side deterministic output validation rejects a reply before artifacts
exist, the harness records failed mandatory checks with an explicit
**"rejected before check bundle"** reason, matching the runner's failure path.
It does not claim the independent bundle ran. Delivery's malformed narrative test
exercises this real carrier validation; its assembled report cannot acquire a
model-invented heading. Arbitrary unsupported prose is not generally detected by
Delivery's deterministic checks and still needs semantic review.

## Python API

Run from the parent directory with this repository on `PYTHONPATH`:

```python
from cclib.harness import Harness, ScriptedModel

h = Harness()
try:
    request_ref = h.capture(b"Your request text")
    # Build the declared qualified intake and a scripted Intent reply, or load
    # supplied artifacts with their exact IDs using h.capture(raw, record_id=...).
    result = await h.run_stage("intent", {"request": intake},
                               model=ScriptedModel([intent_reply, verifier_reply]),
                               input_refs={"request": intake_ref})
finally:
    h.close()
```

`harness.run_stage(stage, inputs, model_name)` is the synchronous convenience API.
Supply `model=ScriptedModel(...)` for offline runs. An existing event loop should
use `await Harness.run_stage(...)`. Callers can use one Harness for multiple stages
and pass previous `output_refs` as exact input refs. Required blobs must be captured
first; the harness never fabricates missing content or repairs supplied hashes.
`ScriptedModel` accepts strings, JSON values or `(prompt, system)` callbacks.

Results include `status`, `output`, `output_refs`, `check_results`,
`verifier_findings`, `prompts` (role, text, SHA-256, separate system/payload),
`model_calls` (attempt count), `calls` (raw replies/errors/tokens), `tokens`,
`reasons`, `gate_decisions`, `scratch` and a conservative offline label.
Unknown token counts are `null`, never silently zero. Full results are returned;
the caller can persist their JSON. A semantic failure preserves actual findings.

## Optional live adapter — implemented, NOT run during development

`CodexModel(model_name, execute=True)` or CLI `--execute` explicitly permits
model effects. Without opt-in, live construction fails before any subprocess.
Each call uses exactly:

```text
codex exec --skip-git-repo-check -m <model> -s read-only --ephemeral -C <fresh .scratch dir> -o <outfile> -
```

The framed UTF-8 prompt goes to stdin; hard subprocess timeout is 300 seconds.
There are no adapter retries. Raw output, stdout/stderr, prompt and any
`tokens used` line are retained. A nonzero exit, missing output or timeout halts.
Planner's worker may generate a second candidate by design; this is recorded as
another call and is not a hidden transport retry. Screening/Delivery have two
output artifacts, so a clean run makes one worker call and two verifier calls.

CLI input JSON contains `inputs`, optional `input_refs`, and optional `blobs`
entries with `ref` plus UTF-8 `text` or `base64`. Example invocation (not executed):

```powershell
python -B -m cclib.harness intent cclib/case.json --model gpt-6.1-sol --execute
```

## Export prompt comparison

```powershell
python -B -m cclib.compare_prompts <artifacts/readable-or-originals.zip>
```

Reads originals.zip without extracting. Replays captured worker replies through
the current worker and real checks/gates; model calls remain scripted. Finds the
original prompt.txt by exact subnode identity and compares raw UTF-8 bytes without
normalizing JSON, whitespace or line endings. Reports hashes, lengths, equality,
first differing byte, bounded unified diff, readable mirrors and gate actions.
Embedded input objects/text are recovered from original payloads only when their
computed hash matches the requested Ref. Missing bytes are never invented.

The supplied product export yields **4/4 identical prompts**: Intent worker,
Intent verifier, Requirements worker, Requirements verifier. Intent's gate also
matches (`advance`). Requirements' full replay **halts** while the product
advanced: two referenced resource blobs are absent from the export. Their exact
identities appear in `prompt-comparison.json`. Its verifier prompt comparison is
explicitly a separate replay on captured product output, not a gate pass.
Byte equality is evidence for these four prompts only, not all cases or models.

## Offline validation

`verify.py` runs the requested Python interpreter with the exact repository
`PYTHONPATH` and `PYTHONIOENCODING=utf-8`, disabling bytecode writes. It saves exact
merged test output to `test-output.txt`, and regenerates `prompt-comparison.json`.
Tests cover all six advancing stages and all six defective stages, prompt/call
capture, semantic rejection, blocking readiness, malformed review, exact-byte
diffs, implicit-effect rejection, and a **mocked** Codex command/token/timeout
adapter. No test executes Codex. Fixtures are derived in memory from repository
fixtures; original files remain unchanged. Every test store stays in `.scratch`.

Run `sh scripts/ai4r-bench cclib --out DIR`.
