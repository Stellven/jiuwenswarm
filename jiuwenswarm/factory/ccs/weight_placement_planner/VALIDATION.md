# Validation

## Verify a candidate through the CC v2 host

Run from the repository root. Set `CHECKOUT` to an absolute path to the
candidate's Git checkout and `DIFF_PATH` to the absolute path of the
candidate's Git text diff. For explicit diff input, the checkout must hold
the expected preimage. For working-tree input, set `DIFF_PATH=` so verify
compares staged, unstaged and non-ignored untracked changes against HEAD.

```sh
CC="$PWD/jiuwenswarm/factory/ccs/weight_placement_planner"
mkdir -p "$CC/.cc-state"
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$CC/.cc-state"
~/predemo/venv-factory/bin/python - "$CC" "$CHECKOUT" "${DIFF_PATH:-}" <<'PY'
import json
from pathlib import Path
import sys

from jiuwenswarm.ccv2.ccv2 import Host

capsule = Path(sys.argv[1])
inputs = {"checkout": sys.argv[2]}
if sys.argv[3]:
    inputs["diff_path"] = sys.argv[3]
host = Host(capsule / ".cc-state" / "host", python=sys.executable)
release = host.seal(capsule)
receipt = host.call(release, "verify", inputs,
                    grants=["workspace.read", "process.exec"], timeout=60)
print(f"Release manifest: {host.store / 'releases' / release / 'manifest.json'}")
print(json.dumps(receipt, indent=2))
sys.exit(0 if receipt["state"] == "succeeded" and receipt["outputs"]["done"] else 1)
PY
```

To reproduce the synthetic host smoke check, first initialize a tiny preimage
under the capsule and use the good fixture as the diff.

```sh
CC="$PWD/jiuwenswarm/factory/ccs/weight_placement_planner"
mkdir -p "$CC/.cc-state"
CHECKOUT="$(mktemp -d "$CC/.cc-state/fixture.XXXXXX")"
git -C "$CHECKOUT" init -q
mkdir -p "$CHECKOUT/common"
printf '// stock arguments\n' > "$CHECKOUT/common/arg.cpp"
DIFF_PATH="$CC/tests/fixtures/good.diff"
```

`env_gate` defaults to `LLAMA_PLACEMENT_PLAN`. An optional `markers` array
requests extra INFO substrings in addition to the three built-in markers.
The host seals current files and verifies their SHA-256 digests before
execution. CC v2 material entries declare paths and let the host compute
digests at seal time.

## Interpret the receipt

| Evidence | Stage | Coverage |
| --- | --- | --- |
| Unit tests on synthetic files and logs | fixture | Verifier and helper behavior, including rejection cases. |
| Sealed host receipt, with static checks passing | native CC execution | Apply the Git text diff to the preimage, check allowed paths and protected filenames, and detect the recognized default-off gate idiom and added INFO literals. |
| `new_cpp_syntax` checks | compile | Best-effort C++17 syntax only for new units and headers. Missing compiler, missing includes, or no new C++ can yield skipped. Full compile needs every touched unit built and linked with intended settings. |
| Actual model logs and parity comparisons | runtime acceptance | Verify effective load mode, activation, per-name assignments, rollback and byte parity in a fixed configuration. |
| Actual timing and peak residency for the fixed workload | hardware measurement | Requires an authorized real shell for the intended hardware. |

`done: true` covers the static prerequisites and can coexist with skipped
syntax checks. A host receipt with `state: succeeded` can still carry
`done: false`. This verifier cannot establish gate reachability, routing or
sampling semantics, regex assignment correctness, capacity accounting,
fallback, byte parity or hardware behavior. Confirm the checkout pin and
complete [METHOD.md](METHOD.md) independently. The verifier searches
added lines, so an in-place edit can fail a marker or gate check when those
lines already exist in the preimage. Preserve the original result and
inspect the full source and runtime logs before making an evidence claim.

## Revision checks

## Version 1.1.0 results

- **Fixture** — 13 tests passed (10 verifier and 3 helper tests), including
  help and synthetic success/failure for each helper. Run
  `~/predemo/venv-factory/bin/python -m unittest discover -s tests -v`
  from the capsule directory.
- **Compile** — all four C++ samples passed `g++ -std=c++17 -fsyntax-only`
  with include directories `common`, `src`, `include`, `ggml/include` and
  `vendor` from the stock tree. All three helpers passed
  `~/predemo/venv-factory/bin/python -m py_compile helpers/*.py`.
- **Native CC execution** — a sealed host call on the good synthetic fixture
  returned `state: succeeded` and `done: true`, including the fixture's new
  C++ syntax check. All 24 sealed file SHA-256 digests matched.
- **Factory listing** — `~/predemo/venv-factory/bin/python -m
  jiuwenswarm.factory.cli capsules` from the repository root lists
  `placement.build_weight_placement_planner 1.1.0` as valid.
- **Component schema** — direct jsonschema validation against
  `factory/schemas/component.schema.json` fails. The branch for this pin
  requires `base.pre_integration_patch`, `change.patch`, and
  `change.sha256`. The other branch also requires patches and uses a
  different pin. The component ships as a patch-free spec, and resolving this
  mismatch requires a factory schema change outside the capsule scope.
- **Evidence removed** — the seed and stock snapshot no longer have digest
  or apply/syntax evidence against the pin. The synthetic fixtures retain
  coverage of the verifier's checks. The builder must supply a diff for
  candidate verification.
- **Pending candidate checks** — full llama.cpp build, real Qwen/Granite
  inventory checks, runtime acceptance and hardware measurement need the
  authored candidate and their authorized environments.

## Version 1.1.1 checks

Inspect the verifier's `gate_unset_silence` result.
It recognizes local presence checks for direct `getenv` results. It flags
recognized unset-branch logging and reports `inconclusive` when it cannot trace
a preceding local guard. Check caller-side guards and work before the gate
by reviewing source, and confirm silence with the runtime marker helper.
