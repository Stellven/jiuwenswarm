# Expert weight cache validation

## Invoke verify through the CC v2 Host

Run from the repository root. The command below reproduces the authoring
check with the clean pinned stock checkout and the synthetic signature
fixture. It seals the capsule, runs its native capability with explicit
grants and prints a receipt.

```bash
cd "$HOME/predemo/jiuwenswarm-work"
PY="$HOME/predemo/venv-factory/bin/python"
CC="$PWD/jiuwenswarm/factory/ccs/expert_weight_cache"
mkdir -p "$CC/.cc-state"
STATE="$(mktemp -d "$CC/.cc-state/authoring.XXXXXX")"
"$PY" -B - "$HOME/predemo/llama.cpp-stock" "$CC/tests/fixtures/good.diff" \
  > "$STATE/verify-inputs.json" <<'PYTHON'
import json
import sys
print(json.dumps({"checkout": sys.argv[1], "diff_path": sys.argv[2]}))
PYTHON
TMPDIR="$STATE" "$PY" -B -m jiuwenswarm.ccv2.ccv2 run "$CC" verify \
  --inputs "$STATE/verify-inputs.json" --store "$STATE/host" \
  --trusted-local --grant workspace.read --grant process.exec \
  > "$STATE/verify-receipt.json"
cat "$STATE/verify-receipt.json"
```

Retain the receipt with the task. Remove the temporary sealed copy before
running the factory inventory, which walks all capsule subdirectories.

```bash
rm -r "$STATE/host"
```

For a builder run, replace the two inputs with the absolute paths to the
owned Git checkout root and the authored diff. Supply a diff whose preimage
matches that checkout. Omit `diff_path` to check staged, unstaged and
nonignored untracked edits relative to HEAD. Optional `env_gate` must equal
`LLAMA_EXPERT_CACHE`. Optional `markers` is a JSON array of additional required
INFO prefixes. Check `outputs.done` and each check in the receipt. The host
can successfully execute the verifier and return `done: false`.

| Result | Stage and evidence |
| --- | --- |
| Unittests and helper checks on synthetic inputs | **fixture**. Exercise success, protected paths, missing or commented signatures, default-off syntax, inapplicability, and syntax failures or skips. The helper test invokes a fake one-shot script. |
| Path allowlist, protected paths, Git apply check, default-off declaration and INFO marker scans | **native CC execution**. Checks source signatures and applicability without changing the checkout. The verifier's allowlist is broader than the work-order model-file scope. Confirm that scope by inspection. |
| g++ result for new C++ units and headers | **compile** for attempted syntax checks. A skipped check has no compiler evidence and retains the native CC execution label. The configured engine build must compile all touched units and link the binary. |
| Activation, stats, bypass, failure fallback and exact greedy stdout comparison | **runtime acceptance**. Run the built engine in the authorized real shell with `-lv 4` and the frozen configuration. |
| Paired measurements on the target | **hardware measurement**. Required for speed claims. |

The verifier reads added lines. It cannot establish control-flow default-off
behavior, startup mode, engagement, exact copied bytes, last-reader lifetime,
ledger accounting, fallback, output parity or performance. It also does not
verify the supplied checkout's commit pin. Check the pin before beginning.

## Authoring checks

Run local verification from the repository root with `PY`, `CC` and `STATE`
from the example above.

```bash
TMPDIR="$STATE" "$PY" -B -m unittest discover -s "$CC/tests" -v
for sample in "$CC"/samples/*.cpp; do
  g++ -std=c++17 -fsyntax-only "$sample" || exit 1
done
PYTHONPYCACHEPREFIX="$STATE/pycache" "$PY" -m py_compile "$CC"/helpers/*.py
"$PY" -B -m jiuwenswarm.factory.cli capsules
```

## Version 1.1.0 results

- **Fixture**. 12 tests passed, including nine verifier tests and one test
  per helper covering each helper's `--help` and positive and negative cases.
- **Native CC execution**. The sealed Host returned `done: true` for the
  synthetic fixture on pinned stock. Five static checks and the fixture C++
  syntax probe passed. The Host recomputed the release digest and 23 file
  digests, including all 16 declared materials.
- **Compile**. All four standalone C++ samples passed `g++ -std=c++17
  -fsyntax-only`. All three Python helpers passed `py_compile`.
- Verified 40 source anchors at the pinned stock commit. The marker search
  found literal signatures in the specification, sample and synthetic
  fixtures. The four remaining diffs are test fixtures.
- Draft 2020-12 `jsonschema` validation against
  `jiuwenswarm/factory/schemas/component.schema.json` rejects the patch-free
  component spec. The applicable schema branch requires
  `base.pre_integration_patch`, `change.patch` and `change.sha256`. That schema
  is outside this capsule. Factory CC declaration discovery lists 1.1.0 as valid.
- No configured engine build, implementation lifetime replay, live server
  parity, activation or hardware measurement was performed in this revision.

## Version 1.1.1 checks

Inspect the verifier's `gate_unset_silence` result.
It recognizes local presence checks for direct `getenv` results. It flags
recognized unset-branch logging and reports `inconclusive` when it cannot trace
a preceding local guard. Check caller-side guards and work before the gate
by reviewing source, and confirm silence with the runtime marker helper.
