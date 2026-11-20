# Spark demo app

From this checkout, build the frontend and run the app:

```bash
export PATH="$HOME/rsi-native-20261117-setup01/runtime/node-v24.22.3-linux-arm64/bin:$PATH"
cd jiuwenswarm/channels/web/frontend
npm ci --ignore-scripts
npm run build
cd ../../../..
scripts/spark/demo-up
scripts/spark/demo-down
```

The production frontend binds only `100.105.127.48:5173`; its gateway proxy
uses `127.0.0.1:19000`, the gateway control listener `127.0.0.1:19001`, and
AgentServer `127.0.0.1:18092`. User systemd services survive browser reloads and
terminal closure. Logs and PID receipts live in `~/predemo-spark/demo-runtime`.
The app workspace is isolated there; existing user workspaces are untouched.

The Python environment is `.venv` in this checkout. Bring-up attempted `uv venv`
and `uv sync --frozen --no-dev`; GitCode returned HTTP 418 for intelli-router.
The fallback copied the already installed factory-env dependencies into this
isolated environment, then installed this checkout editable with `uv pip
install --no-deps --no-build-isolation -e .`. Its OpenJiuwen receipt points to
exact required commit `9e3390195a9ea15235b2b5f7412cb2aa440622cc`.

Select **Factory runs** in the JiuwenSwarm navigation. Existing native export
bundles are discovered from `~/software-factory-spark-20261113/exports/factory-loop-v1`.
New live homes belong under `~/predemo-spark/factory-runs`. Reviewed launch
JSON templates belong under `~/predemo-spark/launch-templates`; no template is
created by the app. Resource policy, model wrapping and authentication remain
operator-prepared template responsibilities. Never add a model template that
bypasses `bin/capped` or the P0 approval gate. The browser cannot supply commands,
grants or arbitrary file paths. See the [API contract](../../docs/architecture/factory/FACTORY-RUNS-HTTP.md).

Digest badges hash original bytes; previews are sanitized. Missing and changed
files are visible. Replay scrubs the native story projection. Live polling
replaces revised projections. Read-only views do not initialize controllers.
