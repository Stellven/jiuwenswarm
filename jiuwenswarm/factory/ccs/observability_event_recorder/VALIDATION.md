# Capsule validation

## Run the native verifier

From the repo root, use the factory virtualenv and a fresh CC v2 store. The following smoke command uses a synthetic diff that only introduces a tiny new file. It reads the pinned stock checkout and leaves it unchanged.

```sh
cd "$(git rev-parse --show-toplevel)"
export PYTHONDONTWRITEBYTECODE=1
py="${FACTORY_PYTHON:-python}"
capsule="$PWD/jiuwenswarm/factory/ccs/observability_event_recorder"
mkdir -p "$capsule/.cc-state"
scratch="$(mktemp -d "$capsule/.cc-state/verify.XXXXXX")"
cat > "$scratch/inputs.json" <<EOF_INPUT
{"checkout":"$FACTORY_LLAMA_SOURCE","diff_path":"$capsule/tests/fixtures/good.diff"}
EOF_INPUT
"$py" -m jiuwenswarm.ccv2.ccv2 run "$capsule" verify \
    --store "$scratch/store" --inputs "$scratch/inputs.json" \
    --grant workspace.read --grant process.exec --trusted-local
```

For a builder submission, set `checkout` to the absolute root of the owned checkout and `diff_path` to the absolute path of the authored unified Git diff. With `diff_path` omitted, the verifier inspects tracked and nonignored untracked working-tree changes against HEAD. The input may specify `"env_gate":"LLAMA_EVENT_REC"` and a `markers` array of extra required INFO literals. The three lifecycle marker prefixes are always checked. In agent mode use `cc_call` on the prepared `observability.build_runtime_event_recorder@1.1.1` release with capability `verify` and the same inputs.

Read `outputs.done` and the individual `outputs.checks` from the CC receipt. A CC invocation can succeed while the submitted diff fails the checklist. Each check has a name, stage, status and detail.

| Stage label | What the evidence establishes |
| --- | --- |
| fixture | Unit tests exercise synthetic positive and negative diffs and helper inputs. |
| native CC execution | Forward Git apply, the verifier's exact path allowlist and protected-file check, added INFO marker prefixes, and a source check for a gate declaration followed immediately by an absent-value return. Working-tree mode uses a temporary Git index. Explicit patches use a scratch postimage. Review actual path authority and inference semantics separately. |
| compile | The verifier syntax-checks new C++ units with `g++ -std=c++17 -fsyntax-only` and stock include roots. Missing compiler or known generated headers may yield skipped results. Sample and helper syntax checks cover those files only. Use a target build for changed existing units, header dependents and linking. |
| runtime acceptance | Observe the enabled and fallback markers, greedy parity, route/transfer/readiness joins, capacity and overflow, and normal-exit flush in actual inference. The verifier checks source cues and cannot establish these results. |
| hardware measurement | Measure end-to-end recorder overhead on the target hardware with comparable, engaged arms. The verifier collects no timings for this. |

## Version 1.1.0 revision evidence

- **Fixture** — Nine verifier tests and three helper tests passed. Run the suite with `"$py" -B -m unittest discover -s "$capsule/tests" -v`.
- **Native CC execution** — The documented smoke command returned `done: true` with five passing static checks on the pinned stock checkout.
- **Compile** — The synthetic diff's new unit and all three C++ samples passed `g++ -std=c++17 -fsyntax-only`. All three helper scripts passed `python -m py_compile` and their `--help` checks.
- **Package** — The CC v2 host computes SHA-256 digests from current bundle files when it seals the release. The factory CLI command `"$py" -B -m jiuwenswarm.factory.cli capsules` lists the capsule as valid at 1.1.0. Task schema validation passed.
- **Component schema** — The patch-free specification fails the current `jiuwenswarm/factory/schemas/component.schema.json` under `jsonschema`. The observability variant requires `base.pre_integration_patch` and `change.patch` plus `change.sha256` for shipped artifact metadata. The builder specification omits these fields. Catalog validity covers the CC declaration and is independent of component schema validation.
- **Engine evidence** — The removed gate starter no longer has a standalone apply check. A candidate diff is supplied by the adopting builder. Full engine compilation, activation, parity, runtime coverage and loss, and hardware measurements are outside this capsule revision.

## Version 1.1.1 checks

Inspect the verifier's `gate_unset_silence` result.
It recognizes local presence checks for direct `getenv` results. It flags
recognized unset-branch logging and reports `inconclusive` when it cannot trace
a preceding local guard. Check caller-side guards and work before the gate
by reviewing source, and confirm silence with the runtime marker helper.
