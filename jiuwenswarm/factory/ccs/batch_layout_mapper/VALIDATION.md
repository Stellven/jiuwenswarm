# Validation

## Invoke the native verifier

From the repository root, write an inputs file with the absolute path to the owned Git working tree and, for patch mode, the absolute path to the builder's proposed diff.

```json
{
  "checkout": "/absolute/path/to/owned/llama.cpp",
  "diff_path": "/absolute/path/to/proposed.diff",
  "env_gate": "LLAMA_BATCH_LAYOUT",
  "markers": []
}
```

Run the CC v2 host with explicit grants.

```sh
cd ~/predemo/jiuwenswarm-work
capsule="$PWD/jiuwenswarm/factory/ccs/batch_layout_mapper"
~/predemo/venv-factory/bin/python -B -m jiuwenswarm.ccv2.ccv2 run \
  "$capsule" verify --trusted-local \
  --store "$capsule/.cc-state" --inputs /absolute/path/to/inputs.json \
  --grant workspace.read --grant process.exec
```

In explicit diff mode, point `checkout` at the matching preimage working tree. For a proposed change already present in the working tree, omit `diff_path` to compare staged, unstaged, and nonignored untracked changes against HEAD. For a committed change, provide the complete diff and its preimage checkout. `env_gate` defaults to the exact name above. `markers` adds literal strings to the built-in requirements. Approve the path arguments as part of invoking this team-trusted native tool. The host seals SHA-256 digests for all bundled files in the release manifest.

Read the host receipt and then `outputs.done` and `outputs.checks`. A successful host call can return `outputs.done: false`. The host CLI exit status alone does not convey the verifier verdict. `done: true` permits skipped checks, so read each status and detail.

| Result | Stage and scope |
|---|---|
| `apply_check`, `allowed_paths`, `router_and_sampling` | **native CC execution**. Checks Git applicability and the text diff allowlist, and reports forbidden router or sampling files. Review behavior within allowed paths separately. |
| `default_off_getenv`, `activation_markers` | **native CC execution**. Checks the null-guarded exact environment comparison and required added strings. Inspect control flow and log calls to establish that the component actually uses them. |
| `new_file_syntax` or `new_file_syntax:<path>` | **compile** only when the new-file C++17 check runs and passes. The syntax check can skip when no file is new, the compiler or an include is unavailable, or a static check fails. Use the normal build for every touched unit and linking. |
| Packaged unit tests and the host smoke run over a synthetic diff | **fixture** evidence for the builder capsule. The host smoke run exercises the native binding and emits the static and syntax stage tags for the synthetic input. |
| Live activation, output parity, bounds, memory ledger and bypass | **runtime acceptance** via the engine checks in [METHOD.md](METHOD.md). The native verifier does not run the server or check these claims. |
| Timing or physical weight traffic | **hardware measurement** on the target with equivalent settings. The native verifier does not measure hardware. |

## Version 1.1.0 validation

- **fixture** — 10 unit tests passed, seven for the verifier and three for the helpers. A synthetic good diff exercised the CC v2 host and passed five static checks and one C++17 header syntax check. Full engine applicability at `9048bad8` now depends on the builder supplying an actual candidate.
- Standalone checks passed for three C++17 samples with `g++ -std=c++17 -fsyntax-only` and one Python sample with `python -m py_compile`. The length sample also ran. All three helpers passed `py_compile` and `--help`.
- The factory capsule CLI validated the CC declaration and listed `engine.build_batch_layout_mapper` at 1.1.0. All 24 file digests in the sealed release matched the capsule files, including its 15 declared materials.
- Component schema validation with `jsonschema.Draft202012Validator` failed. The schema branch for this pin requires `base.pre_integration_patch`, `change.patch` and `change.sha256`. The other branch requires a patch list and a different pin. The builder specification omits those patch fields.
- Full llama.cpp build and link, runtime activation, sweep parity, live multi-slot bypass, and hardware measurement were outside the worker scope.

The task template links to the local ontology slice and retains the `star-prefill-v0` contract placeholder. The factory plan seeder currently resolves slices from the expert-streaming ontology, which does not include this slice.

## Version 1.1.1 checks

Inspect the verifier's `gate_unset_silence` result.
It recognizes local presence checks for direct `getenv` results. It flags
recognized unset-branch logging and reports `inconclusive` when it cannot trace
a preceding local guard. Check caller-side guards and work before the gate
by reviewing source, and confirm silence with the runtime marker helper.
