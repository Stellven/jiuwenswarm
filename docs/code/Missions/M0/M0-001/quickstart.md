# M0-001 quickstart

The concrete setup, client commands, authenticated API calls and deployment requirements are in [standalone README](../../../../../standalone/intent_compiler/README.md). Use the repository root as working directory. The exact registered feature remains `docs/code/Missions/M0/M0-001`; client/product use does not require Spec Kit.

1. Prepare the authorized input root and existing default `docs/` directory, protected operator-token file, approved native Codex route and persistent state directory.
2. Install `standalone/intent_compiler/requirements.lock`; run `npm --prefix standalone/intent_compiler/frontend ci` and `npm --prefix standalone/intent_compiler/frontend run build`.
3. Set the documented `INTENT_*` configuration, `PYTHONPATH=standalone/intent_compiler`, then run `.venv-intent/Scripts/python.exe -m intent_compiler serve`.
4. Open `http://127.0.0.1:5173`, authenticate, check prerequisites, submit uniquely identified input and inspect status/named evidence. Preserve the client request ID for reconciliation after disconnect.
5. For headless execution use `python -m intent_compiler run --request-file REQUEST --client-request-id CASE --profile compiler-only --timeout 600 --export BUNDLE.zip`. Success requires durable node-released Brief2; a halt exits non-success and exports available evidence.

The optional operator-only `smoke` / `compiler-smoke` configuration is invalid for product acceptance. It exercises the same client/runtime graph but cannot prove semantic model quality. Production prerequisite failures and missing Docker remain explicit blockers in [tasks.md](tasks.md), even when local fixture checks pass.

Connected API checks use `.venv-intent/Scripts/python.exe -m pytest -c standalone/intent_compiler/pytest.ini standalone/intent_compiler/tests/test_api.py -q`; the explicit config isolates these tests from legacy repository plugin/options.

The raw HTTP submission wrapper is separately documented from the host-captured canonical `Client_Submission.json`; all client/readiness/status/retrieval/cancellation/error records retain the supplied field-contract core and namespaced `ext["m0.intent"]` diagnostics. `Run_Bundle.json` snapshots preserve actual state and exact readable evidence references. Corrected requests use a fresh ID and may link `previous_run_id`; no run is silently repaired or replayed.
