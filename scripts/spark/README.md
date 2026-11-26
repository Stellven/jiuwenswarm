# Factory runs helpers

The Factory runs web API (`jiuwenswarm/gateway/channel_manager/web/factory_http.py`) imports these helpers:

- `prepare_inspection_home.py` prepares an isolated factory home for a read-only capsule inspection session. It uses `prepare_star_home.py` to copy the operator's Codex sign-in into that home.
- `recorder_live_demo.py` runs the recorder evidence walkthrough (`recorder-evidence-walkthrough.json`) as a live factory session against retained evidence. It loads no model.
- `build_demo_replays.py` builds the curated replay bundles (`factory.curated-replay/1`) that the Factory runs page shows as one test from contract to result:

  ```bash
  python -m scripts.spark.build_demo_replays --base <run workspace> --out <exports dir> --replace
  ```

Run them from the repository root with the checkout's Python. See the [API contract](../../docs/architecture/factory/FACTORY-RUNS-HTTP.md).

## Serve the Factory demo on Spark

After the lead retires the prior local instance on port 5175, run from the
integrated checkout with its Python environment and the offline-built frontend:

```bash
python -m scripts.spark.factory_demo_web \
  --dist jiuwenswarm/channels/web/frontend/dist \
  --live ~/muse-demo/graph-r8 \
  --history ~/muse-demo/graph-v4
```

Use `http://127.0.0.1:5175/factory` for Factory Runs and
`http://127.0.0.1:5175/fallback?mode=live` for the read-only plain board. One
loopback listener serves the compiled frontend, the native WebChannel on `/ws`,
Factory HTTP under `/api/factory`, and the board's existing API paths. The demo
host provides local WebChannel requests and leaves agent-backed chat unavailable. The web
host uses the recorded graph-r8 home and presents graph-v4 as read-only history.
`--extra-root PATH` adds an optional historical export directory or home.

To verify the same app without binding a TCP port, pass `--socket` with a socket
path in a private directory and use `curl --unix-socket PATH http://localhost/factory`.
The standalone `python -m jiuwenswarm.factory.demo_board` command remains
available for the plain board by itself.
