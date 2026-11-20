# Expert demand predictor validation

## Invoke the native capability

From the repository root, run the following fixture smoke check. It uses the CC v2 host to seal the bundle and invoke `verify` against the pinned stock Git root with a synthetic diff. The host records its receipt below the capsule's ignored `.cc-state` directory.

```sh
cd ~/predemo/jiuwenswarm-work
capsule="$PWD/jiuwenswarm/factory/ccs/expert_demand_predictor"
mkdir -p "$capsule/.cc-state/tmp"
TMPDIR="$capsule/.cc-state/tmp" PYTHONDONTWRITEBYTECODE=1 \
  ~/predemo/venv-factory/bin/python - "$capsule" "$HOME/predemo/llama.cpp-stock" \
  "$capsule/tests/fixtures/good.diff" <<'PY'
import json
from pathlib import Path
import sys

from jiuwenswarm.ccv2.ccv2 import Host

capsule, checkout, *patch = sys.argv[1:]
inputs = {"checkout": checkout}
if patch:
    inputs["diff_path"] = patch[0]
host = Host(Path(capsule) / ".cc-state" / "verify-host", python=sys.executable)
receipt = host.run(capsule, "verify", inputs,
                   grants=["workspace.read", "process.exec"], timeout=60)
print(json.dumps(receipt, indent=2))
PY
```

For a candidate, replace the checkout and diff arguments with absolute paths to the owned Git root at the intended base and the authored diff. In explicit mode the verifier checks against the checkout's current files. Omit the last argument to inspect uncommitted work relative to `HEAD`, including non-ignored untracked files. Optional inputs are `env_gate`, which accepts `LLAMA_EXPERT_PREDICT`, and `markers`, an array of additional required literal substrings.

## Read the verdict

| Stage | Meaning |
| --- | --- |
| fixture | Synthetic input exercises the checker. The host smoke invocation above demonstrates native dispatch on fixture data, including compilation of a toy C++ unit. |
| native CC execution | On a candidate, checks report applyability, allowed regular text changes, protected filenames, the recognized guarded exact-value `getenv` idiom and marker substrings in added C++ string literals. A succeeded receipt establishes execution. Inspect `outputs.done` and every check's status for the source verdict. |
| compile | The verifier performs best-effort `g++ -std=c++17 -fsyntax-only` against scratch postimages and checkout headers. A skipped compiler check can leave static `done` true. A syntax pass covers only the units and flags reported. A separate configured target build covers the affected units and dependencies. |
| runtime acceptance | Live logs, matched greedy and routing evidence, failure and cap cases, and held-out captured trace results earn this stage. The verifier cannot establish these results, callback control flow, INFO visibility, the effective load mode or readiness at consumption. |
| hardware measurement | Collect matched repetitions on the target under the frozen contract. |

The verifier allows the work order's optional `tools/server/server-context.cpp`
and protects model source. Review server changes for a bounded slot and prefill
phase handoff with an unchanged stock decode dispatch. The server translation
unit needs the configured target include paths and is skipped by the standalone
syntax probe. Confirm the source pin separately.

## Version 1.1.0 revision results on Satay

- **Fixture** — 9 unit tests passed, including 6 verifier cases and 3 helper cases. Three helper modules passed `python -m py_compile` and three `--help` calls succeeded. Synthetic replay yielded 4 hits and 3 misses.
- **Native CC execution** — The exact host call above succeeded. All five static checks and the fixture syntax check passed. The factory CLI listed `routing.build_expert_demand_predictor 1.1.0` as native and valid. The host sealed all 16 declared materials with fresh file hashes. The removed starter no longer supplies a patch or syntax smoke check on its own code.
- **Compile** — Each of `env_gate.cpp`, `info_markers.cpp`, `frequency_rank.cpp` and `outcome_counts.cpp` passed standalone `g++ -std=c++17 -fsyntax-only`.
- **Component schema** — `jsonschema` rejected the patch-free specification against the unchanged `jiuwenswarm/factory/schemas/component.schema.json`. Its observability layout requires patch filenames and hashes for both the pre-integration and change records. Its other layout requires a patch list and a different source commit. The patch-free component needs an update to the shared schema.
- **Pending builder evidence** — Target compile, server activation, greedy and routing parity, live fallback and caps, held-out captured-trace replay and hardware measurement remain pending. The worker ran no engine build or server.

## Version 1.1.1 checks

Inspect the verifier's `gate_unset_silence` result.
It recognizes local presence checks for direct `getenv` results. It flags
recognized unset-branch logging and reports `inconclusive` when it cannot trace
a preceding local guard. Check caller-side guards and work before the gate
by reviewing source, and confirm silence with the runtime marker helper.
